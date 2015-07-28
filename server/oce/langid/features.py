# Online Corpus Editor
# Language Identification: Features

import re
import string

import enchant
import nltk

import oce.logger

logger = oce.logger.getLogger(__name__)

# === Config ===
from oce.config import sge_words, sge_chinese_derived_words
from oce.config import valid_pinyin

# === Spellcheckers ===
enchant.set_param("enchant.myspell.dictionary.path", "./lib/dict")
# --- Languages and minor variants ---
spelling_languages = {
    "en": ["en_US-large", "en_GB-large"],
    "ms": ["ms_MY"],
    "sge": [],
    "zh": []
    # "sge" and "zh" handled with personal word lists below
}
# --- Corresponding dictionaries ---
spelling_dictionaries = {}
for language in spelling_languages.keys():
    spelling_dictionaries[language] = {}
    for variant in spelling_languages[language]:
        spelling_dictionaries[language][variant] = enchant.Dict(variant)
# --- SgE word lists ---
spelling_dictionaries["sge"] = {}
sge_lists = sge_words + sge_chinese_derived_words
for wordlist in sge_lists:
    spelling_dictionaries["sge"][wordlist] = enchant.request_pwl_dict(wordlist)
# --- Additional word list handling ---
# Count Chinese-derived words in SgE as Chinese
for wordlist in sge_chinese_derived_words:
    spelling_dictionaries["zh"][wordlist] = enchant.request_pwl_dict(wordlist)


def extract_features(sentence):
    tokenised = tokenise(sentence)
    tokenised_spellcheck = prep_tokens_for_spellcheck(tokenised)
    features = {}
    ## Primary features
    # Chinese
    features["has_zh_chars"] = has_zh_chars(sentence)
    features["has_pinyin"] = has_pinyin(tokenised_spellcheck)
    features["has_spelling_zh"] = has_spelling_language(tokenised_spellcheck,
                                                        "zh")
    # Singlish
    features["has_spelling_sge"] = has_spelling_language(tokenised_spellcheck,
                                                         "sge")
    features["has_z_ending_word"] = has_z_ending_word(tokenised)
    # English
    features["has_spelling_en"] = has_spelling_language(tokenised_spellcheck,
                                                        "en")
    # Malay
    features["has_spelling_ms"] = has_spelling_language(tokenised_spellcheck,
                                                        "ms")

    features = add_binary_portion_language(features, tokenised_spellcheck, 1,
                                           "en")
    features = add_binary_portion_language(features, tokenised_spellcheck, 1,
                                           "ms")

    ## Consolidated features
    # Chinese
    features["has_zh"] = (features["has_zh_chars"] or
                          features["has_pinyin"] or
                          features["has_spelling_zh"])
    # Singlish
    features["has_sge"] = (features["has_spelling_sge"] or
                           features["has_z_ending_word"])
    # English
    features["has_en"] = (features["has_spelling_en"])
    # Malay
    features["has_ms"] = (features["has_spelling_ms"])

    ## Language mixes
    # English-Chinese
    features["has_en_zh"] = (features["has_zh"]
                             and
                             features["has_en"])
    # English-Malay
    features["has_en_ms"] = (features["has_ms"]
                             and
                             features["has_en"])
    # Singlish-Chinese
    features["has_sge_zh"] = (features["has_zh"]
                              and
                              features["has_sge"])
    # Singlish-Malay
    features["has_sge_ms"] = (features["has_ms"]
                              and
                              features["has_sge"])
    # English-Chinese-Malay (Unlikely?)
    features["has_en_zh_ms"] = (features["has_en"]
                                and
                                features["has_zh"]
                                and
                                features["has_ms"])
    return features


# === Generic Functions ===
def tokenise(sentence):
    ## General pre-processing
    # Remove common URL patterns from our sentence.
    logger.debug("Tokenising: '" + sentence + "'")
    sentence = re.sub(r'https?://[^ ]*', '', sentence)
    logger.debug("URLs removed: '" + sentence + "'")

    # For now, just use the default nltk tokeniser
    # TODO: Try the pyenchant tokeniser
    tokenised = nltk.tokenize.word_tokenize(sentence)

    ## General token processing
    # Split words with slashes into multiple tokens
    temp = []
    for token in tokenised:
        split = token.split("/")
        temp = temp + split
    tokenised = temp

    # Remove punctuation, then whitespace.
    tokenised = [token.strip("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~").strip() for
                 token in tokenised]

    # Drop empty tokens and return
    return [token for token in tokenised if token != '']


def prep_tokens_for_spellcheck(tokenised):
    # Specific pre-processing steps needed for spellcheckers

    # Drop non-printable characters and numerals
    # (TBH, we should probably drop even more)
    printable = set(string.printable) - set("0123456789")
    tokenised = [''.join([char for char in token if char in printable])
                 for token in tokenised]

    # Words to ignore, including the empty string
    blacklist = {""}
    # Twitter jargon (should always be in uppercase?)
    blacklist.add("USERNAME")
    blacklist.add("RT")

    tokenised = [token for token in tokenised if token not in blacklist]
    logger.debug("Tokens for spellchecking: [" + '], ['.join(tokenised) + "]")
    return tokenised


def word_in_dictionary(word, language):
    dictionaries = spelling_dictionaries[language]

    # Checks common variants of the word
    to_check = [word, word.upper(), word.lower(), word.title()]

    for lang_variant, dictionary in dictionaries.items():
        for variant in to_check:
            if dictionary.check(variant):
                logger.debug(
                    "Found '{0}' in dictionary: '{1}'".format(
                        variant, lang_variant)
                )
                return True
    return False


def word_in_dictionary_unique(word, main_language):
    """
    Returns true only if the given word does *not* show up in any of the other dictionaries loaded
    Dictionaries are grouped by family (so, for example, en_GB and en_US don't cancel each other out here)
    """
    other_languages = [lang for lang in spelling_dictionaries.keys() if
                       lang != main_language]

    # Step 1: Is the word even in the specified dictionary?
    if not word_in_dictionary(word, main_language):
        return False

    # Step 2: Check against all the other dictionaries, returning asap
    for other_language in other_languages:
        if word_in_dictionary(word, other_language):
            return False
    return True


def has_spelling_language(tokenised, language):
    for token in tokenised:
        if word_in_dictionary(token, language):
            logger.debug(
                "Found word '{0}' for language: {1}".format(
                    token, language)
            )
            return True
    return False


def has_spelling_language_unique(tokenised, language):
    for token in tokenised:
        if word_in_dictionary_unique(token, language):
            logger.debug(
                "Found unique word '{0}' for language: {1}".format(
                    token, language)
            )
            return True
    return False


def portion_spelling_language(tokenised, precision, language):
    """
    Find the fraction of the tokens that were found in the specified
    dictionary.
    Returns a float between 0 and 1 rounded to the precision specified.
    :param tokenised:
    :param precision: The number of decimal places to round to
    :param language:
    :return:
    """
    # The prepared sentence will sometimes be empty (e.g., if it consists solely of non-printable characters)
    if len(tokenised) == 0:
        return 0

    yes = 0
    no = 0
    for token in tokenised:
        if word_in_dictionary(token, language):
            yes += 1
        else:
            no += 1
    rounded = "{:.{precision}f}".format(yes / (yes + no), precision=precision)
    return float(rounded)


def portion_spelling_language_unique(tokenised, precision, language):
    """
    This version only takes into account the words unique to the given
    language and the words that don't appear in it.
    Non-unique words (i.e., words that show up under the dictionaries for
    multiple languages) are ignored.
    """
    if len(tokenised) == 0:
        return 0

    yes = 0
    no = 0
    for token in tokenised:
        if word_in_dictionary(token, language):
            if word_in_dictionary_unique(token, language):
                yes += 1
        else:
            no += 1
    rounded = "{:.{precision}f}".format(yes / (yes + no), precision=precision)
    return float(rounded)


def add_binary_portion_language(featureset, tokenised, precision, language):
    # Step 0: Get the actual portion
    portion = portion_spelling_language(tokenised, precision, language)

    # Step 1: Find all the precision steps
    steplist = [n / (10 ** precision) for n in range(1, 10 ** precision + 1)]
    for step in steplist:
        if portion < step:
            featureset[language + "_at_least_" + str(step)] = False
        else:
            featureset[language + "_at_least_" + str(step)] = True
    return featureset


def add_binary_portion_language_unique(featureset, tokenised, precision,
                                       language):
    # Step 0: Get the actual portion
    portion = portion_spelling_language_unique(tokenised, precision, language)

    # Step 1: Find all the precision steps
    steplist = [n / (10 ** precision) for n in range(1, 10 ** precision + 1)]
    for step in steplist:
        if portion < step:
            featureset[language + "_at_least_" + str(step)] = False
        else:
            featureset[language + "_at_least_" + str(step)] = True
    return featureset


# === Chinese ===
def has_zh_chars(str):
    for c in str:
        cjk = ord(u'\u4e00') <= ord(c) <= ord(u'\u9fff')
        cjka = ord(u'\u3400') <= ord(c) <= ord(u'\u4dbf')
        cjkb = ord(u'\U00020000') <= ord(c) <= ord(u'\U0002A6DF')
        cjkc = ord(u'\U0002A700') <= ord(c) <= ord(u'\U0002B73F')
        cjkd = ord(u'\U0002B740') <= ord(c) <= ord(u'\U0002B81F')
        cjke = ord(u'\U0002B820') <= ord(c) <= ord(u'\U0002CEAF')
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

    # logger.debug("Checking for pinyin: " + word)

    # Step 0: See if it is one of a few exceptions without an initial:
    # a, o, e, ai, ei, ao, ou, an, ang, en, eng
    pattern = r"a(([io]|ng?)?|ou?|e(i|ng?)?)$"
    if re.match(pattern, word) is not None:
        logger.debug("'" + word + "' looks like valid pinyin. (No initial)")
    else:
        # Step 1: Parse initial/final
        pattern = r"([bpmfdtnlgkhrjqxwy]|[zcs]h?)(.*)"
        match = re.match(pattern, word)
        if match is None:
            # logger.debug("Initial was not valid: " + word)
            return False
        initial = match.group(1)
        final = match.group(2)
        # logger.debug("Initial: " + initial + "; Final: " + final)

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
            # logger.debug("Final was not valid: " + word)
            return False

        if re.match(pattern, final) is None:
            # logger.debug("Final was not valid: " + word)
            return False

        # Step 3: See if initial and final are compatible
        if final in valid_pinyin[initial]:
            logger.debug("'" + word + "' looks like valid pinyin.")
        else:
            # logger.debug("Initial-Final combination was not valid: " + word)
            return False

    # Step 4: Check it against our other dictionaries; better safe than sorry?
    # We expect to see pinyin for 'zh' and 'sge' records
    other_languages = [x for x in spelling_dictionaries.keys()
                       if x != 'zh' and x != 'sge']
    for language in other_languages:
        if word_in_dictionary(word, language):
            logger.debug(
                "... But found '{0}' in dictionary: {1}".format(word, language)
            )
            return False

    # Step 5: Our word didn't fail on any of the short circuit checks; take it
    # as valid pinyin
    return True


def has_pinyin(tokenised):
    for token in tokenised:
        if check_pinyin(token):
            return True
    return False


# === Singlish ===
def has_z_ending_word(tokenised):
    for token in tokenised:
        if token.endswith('z'):
            return True
    return False
