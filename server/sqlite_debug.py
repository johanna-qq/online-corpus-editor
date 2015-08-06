import sqlite3
import zlib
import hashlib
import re

import oce.logger

logger = oce.logger.getLogger(__name__)


def main():
    logger.info("Starting")
    conn = sqlite3.connect("data/sge_tweets.db")
    conn.create_function("tokenise", 1, tokenise)
    conn.create_function("suffixes", 1, tokenise_and_extract_suffixes)
    c = conn.cursor()
    return conn, c


def tokenise(value):
    if not isinstance(value, str):
        # Don't touch anything that isn't a string
        return value

    # Emulate SQLite's simple tokeniser:
    # Everything is lowercase, and all non-alphanumeric ASCII characters are
    # treated as delimiters (via replace_non_alphanumeric_chars)
    # TODO: Treat emoticons separately.
    value = value.lower()
    value = re.sub(r"[^a-zA-Z0-9]", replace_non_alphanumeric_chars, value)

    # Get rid of extra whitespace
    value = " ".join(value.split())

    return value


def tokenise_and_extract_suffixes(value):
    if not isinstance(value, str):
        # Don't touch anything that isn't a string
        return value

    value = tokenise(value)

    suffixes = []
    words = value.split()
    for word in words:
        end_pos = len(word)
        if end_pos == 1:
            continue
        for start_pos in range(1, end_pos):
            suffixes.append(word[start_pos:end_pos])
    suffixes = ' '.join(suffixes)
    return suffixes


def replace_non_alphanumeric_chars(matchobj):
    """
    Takes an re.match on r'[^a-zA-Z0-9]'
    """
    char = matchobj.group(0)
    # If char is within the ASCII range, treat it as a delimiter.
    if ord(char) <= 127:
        return " "
    # If it is not, treat each unicode character as a separate token by
    # inserting a delimiter before it
    return " " + char


def do_it(fn):
    import timeit
    start_time = timeit.default_timer()
    value = fn()
    print(str(value))
    print("Took: {:.3f}s".format(timeit.default_timer() - start_time))


# https://github.com/hideaki-t/sqlite-fts-python
