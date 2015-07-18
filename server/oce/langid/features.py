# Online Corpus Editor
# Language Identification: Features

import re

import enchant
import nltk

import oce

logger = oce.getLogger(__name__)

# === Config ===
from oce.config import sge_words
from oce.config import valid_pinyin

# === Spellcheckers ===
en_US = enchant.Dict("en_US")
en_GB = enchant.Dict("en_GB")
sge_lists = [enchant.request_pwl_dict(pwl) for pwl in sge_words]


def extract_features(sentence):
    tokenised = tokenise(sentence)
    features = {}
    # Primary features
    features["has_zh"] = has_zh(sentence)
    features["has_pinyin"] = has_pinyin(tokenised)
    features["has_en_US"] = has_en_US(tokenised)
    features["portion_en_US_1"] = portion_en_US(tokenised, 1)
    features["has_en_GB"] = has_en_GB(tokenised)
    features["portion_en_GB_1"] = portion_en_GB(tokenised, 1)
    features["has_sge_words"] = has_sge_words(tokenised)

    # Secondary features
    features["has_en_and_zh"] = ((features["has_zh"])
                                 and
                                 (features["has_en_US"] or
                                  features["has_en_GB"] or
                                  features["has_sge_words"]))
    return features


def tokenise(sentence):
    """
    Returns a tokenised version of the sentence
    :param sentence:
    :return:
    """
    # For now, just use the default nltk tokeniser
    # TODO: Try the pyenchant tokeniser
    return nltk.tokenize.word_tokenize(sentence)


def has_zh(str):
    for c in str:
        cjk = u'\u4e00' <= c <= u'\u9fff'
        cjka = u'\u3400' <= c <= u'\u4dbf'
        cjkb = u'\u20000' <= c <= u'\u2A6DF'
        cjkc = u'\u2A700' <= c <= u'\u2B73F'
        cjkd = u'\u2B740' <= c <= u'\u2B81F'
        cjke = u'\u2B820' <= c <= u'\u2CEAF'
        if cjk or cjka or cjkb or cjkc or cjkd or cjke:
            return True
    return False


def check_pinyin(word):
    """
    Returns True if a word looks like (Mandarin) pinyin
    (http://pinyin.info/rules/initials_finals.html)
    :param word:
    :return:
    """

    logger.debug("Checking for pinyin: " + word)

    # Step 0: See if it is one of a few exceptions without an initial:
    # a, o, e, ai, ei, ao, ou, an, ang, en, eng
    pattern = r"a([io]|ng?)?|ou?|e(i|ng?)?"
    if re.match(pattern, word) is not None:
        logger.debug("'" + word + "' looks like valid pinyin. (No initial)")
        return True

    # Step 1: Parse initial/final
    pattern = r"([bpmfdtnlgkhrjqxwy]|[zcs]h?)(.*)"
    match = re.match(pattern, word)
    if match is None:
        logger.debug("Initial was not valid: " + word)
        return False
    initial = match.group(1)
    final = match.group(2)
    logger.debug("Initial: " + initial + "; Final: " + final)

    # Step 2: Check final
    # a, ai, ao, an, ang
    a_pattern = r"a([io]|ng?)?"
    # o, ou, ong
    o_pattern = r"o(u|ng)?"
    # e, ei, en, eng
    e_pattern = r"e(i|ng?)?"
    # u, ua, uo, uai, ui, uan, uang, un, ueng*
    # *: romanised as w + eng
    u_pattern = r"u(a(i|ng?)?|o|i|n)?"
    # i, ia, ie, iao, iu, ian, iang, in, ing, iong
    i_pattern = r"i(a(o|ng?)?|e|u|ng?|ong)?"
    # v, ve
    v_pattern = r"ve?"

    # Final may end with a tone number (liberally, 0-5 including light tone)
    final = final.rstrip("012345")
    if final.startswith("a"):
        pattern = a_pattern
    elif final.startswith("o"):
        pattern = o_pattern
    elif final.startswith("e"):
        pattern = e_pattern
    elif final.startswith("u"):
        pattern = u_pattern
    elif final.startswith("i"):
        pattern = i_pattern
    elif final.startswith("v"):
        pattern = v_pattern
    else:
        logger.debug("Final was not valid: " + word)
        return False

    if re.match(pattern, final) is None:
        logger.debug("Final was not valid: " + word)
        return False

    # Step 3: See if initial and final are compatible
    if final in valid_pinyin[initial]:
        logger.debug("'" + word + "' looks like valid pinyin.")
        return True
    else:
        logger.debug("Initial-Final combination was not valid: " + word)
        return False


def has_pinyin(tokenised):
    for token in tokenised:
        if check_pinyin(token):
            return True
    return False


def has_en_US(tokenised):
    for token in tokenised:
        if en_US.check(token):
            return True
    return False


def portion_en_US(tokenised, precision):
    """
    Find the fraction of the tokens that were found in the en_US
    dictionary.
    Returns a float between 0 and 1 rounded to the precision specified.
    :param tokenised:
    :param precision: The number of decimal places to round to
    :return:
    """
    yes = 0
    no = 0
    for token in tokenised:
        if en_US.check(token):
            yes += 1
        else:
            no += 1
    rounded = "{:.{precision}f}".format(yes / (yes + no), precision=precision)
    return float(rounded)


def has_en_GB(tokenised):
    for token in tokenised:
        if en_GB.check(token):
            return True
    return False


def portion_en_GB(tokenised, precision):
    """
    Find the fraction of the tokens that were found in the en_GB
    dictionary.
    Returns a float between 0 and 1 rounded to the precision specified.
    :param tokenised:
    :param precision: The number of decimal places to round to
    :return:
    """
    yes = 0
    no = 0
    for token in tokenised:
        if en_GB.check(token):
            yes += 1
        else:
            no += 1
    rounded = "{:.{precision}f}".format(yes / (yes + no), precision=precision)
    return float(rounded)


def has_sge_words(tokenised):
    for token in tokenised:
        for list in sge_lists:
            if list.check(token):
                return True
    return False
