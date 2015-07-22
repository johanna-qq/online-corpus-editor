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
enchant.set_param("enchant.myspell.dictionary.path","./lib/dict")
en_US = enchant.Dict("en_US")
en_GB = enchant.Dict("en_GB")
ms_MY = enchant.Dict("ms_MY")

dictionary_list = ["en_US", "en_GB", "ms_MY"]
dictionaries = {}
for language in dictionary_list:
    dictionaries[language] = enchant.Dict(language)

sge_lists = [enchant.request_pwl_dict(pwl) for pwl in sge_words]


def extract_features(sentence):
    tokenised = tokenise(sentence)
    features = {}
    ## Primary features
    # Chinese
    features["has_zh_chars"] = has_zh_chars(sentence)
    features["has_pinyin"] = has_pinyin(tokenised)
    # English
    features["has_en_US"] = has_en_US(tokenised)
    features["portion_en_US_1"] = portion_en_US(tokenised, 1)
    features["has_en_GB"] = has_en_GB(tokenised)
    features["portion_en_GB_1"] = portion_en_GB(tokenised, 1)
    # Singlish
    features["has_sge_words"] = has_sge_words(tokenised)
    # Malay
    features["has_ms_MY"] = has_ms_MY(tokenised)
    features["portion_ms_1"] = portion_ms_MY(tokenised, 1)

    ## Secondary features
    # Chinese
    features["has_zh"] = (features["has_zh_chars"] or
                            features["has_pinyin"])
    features["no_zh"] = not features["has_zh"]
    # English
    features["has_en"] = (features["has_en_US"] or
                                  features["has_en_GB"])
    features["no_en"] = not features["has_en"]
    # Singlish
    features["has_sge"] = (features["has_sge_words"])
    features["no_sge"] = not features["has_sge"]
    # Malay
    features["has_ms"] = (features["has_ms_MY"])
    features["no_ms"] = not features["has_ms"]

    # English-Chinese
    features["has_en_zh"] = (features["has_zh"]
                                 and
                                 features["has_en"])
    # English-Malay
    features["has_en_ms"] = (features["has_ms"]
                                 and
                                 features["has_en"])
    # English-Chinese-Malay
    features["has_en_zh_ms"] = (features["has_en"]
                                 and
                                 features["has_zh"]
                                 and
                                 features["has_ms"])
    return features


def tokenise(sentence):
    """
    Returns a tokenised version of the sentence
    :param sentence:
    :return:
    """
    # For now, just use the default nltk tokeniser
    # TODO: Try the pyenchant tokeniser
    tokenised = nltk.tokenize.word_tokenize(sentence)

    # Pre-processing

    # Done
    return tokenised



def has_zh_chars(str):
    for c in str:
        cjk = ord(u'\u4e00') <= ord(c) <= ord(u'\u9fff')
        cjka = ord(u'\u3400') <= ord(c) <= ord(u'\u4dbf')
        cjkb = ord(u'\U00020000') <= ord(c) <= ord(u'\U0002A6DF')
        cjkc = ord(u'\U0002A700') <= ord(c) <= ord(u'\U0002B73F')
        cjkd = ord(u'\U0002B740') <= ord(c) <= ord(u'\U0002B81F')
        cjke = ord(u'\U0002B820') <= ord(c) <= ord(u'\U0002CEAF')
        if cjk or cjka or cjkb or cjkc or cjkd or cjke:
            print("zh_char: " + c)
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
    pattern = r"a(([io]|ng?)?|ou?|e(i|ng?)?)$"
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
    else:
        logger.debug("Initial-Final combination was not valid: " + word)
        return False

    # Step 4: Check it against our other dictionaries; better safe than sorry?
    for language in dictionaries.keys():
        if dictionaries[language].check(word):
            # TODO: dictionary name
            logger.debug("Found '" + word + "' in dictionary: " + language)
            return False

    return True


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

def has_ms_MY(tokenised):
    for token in tokenised:
        if ms_MY.check(token):
            return True
    return False


def portion_ms_MY(tokenised, precision):
    """
    Find the fraction of the tokens that were found in the ms_MY
    dictionary.
    Returns a float between 0 and 1 rounded to the precision specified.
    :param tokenised:
    :param precision: The number of decimal places to round to
    :return:
    """
    yes = 0
    no = 0
    for token in tokenised:
        if ms_MY.check(token):
            yes += 1
        else:
            no += 1
    rounded = "{:.{precision}f}".format(yes / (yes + no), precision=precision)
    return float(rounded)