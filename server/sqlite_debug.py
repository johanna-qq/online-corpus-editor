import sqlite3
import zlib
import hashlib
import re

import oce.logger

logger = oce.logger.getLogger(__name__)


def main():
    logger.info("Starting")
    conn = sqlite3.connect('data/sge_tweets.db')
    conn.create_function('s_compress', 1, compress_suffix)
    conn.create_function('s_decompress', 1, uncompress_suffix)
    conn.create_function("md5", 1, md5sum)
    conn.create_function("suffixes", 1, tokenise_and_extract_suffixes)
    c = conn.cursor()
    # c.executescript("""
    #     DROP TABLE IF EXISTS fts_test;
    #
    #     CREATE VIRTUAL TABLE fts_test USING fts4(
    #         content="tweets",
    #         ROWID     INTEGER,
    #         fullscan  INTEGER,
    #         content   TEXT,
    #         flag      BOOLEAN,
    #         category  INTEGER,
    #         comment   TEXT,
    #         tag       TEXT,
    #         language  TEXT,
    #         suffixes  TEXT,
    #         tokenize=porter,
    #         compress=s_compress,
    #         uncompress=s_uncompress
    #     );
    #
    #     INSERT INTO fts_test(fts_test) VALUES('rebuild');
    # """)
    return conn, c


def compress_suffix(value):
    if not isinstance(string, str):
        return string
    print("Compress: {}".format(string))
    return string


def uncompress_suffix(string):
    if not isinstance(string, str):
        return string
    print("Uncompress: {}".format(string))
    return string


def md5sum(t):
    return hashlib.md5(str(t).encode()).hexdigest()


def tokenise_and_extract_suffixes(value):
    if not isinstance(value, str):
        # Don't touch anything that isn't a string
        return value

    # Emulate SQLite's simple tokeniser:
    # Everything is lowercase, and all non-alphanumeric ASCII characters are
    # treated as delimiters.
    # FIXME: Don't drop non-ASCII characters
    value = value.lower()
    value = re.sub(r'[^a-zA-Z0-9]', " ", value)

    suffixes = []
    words = value.split()
    for word in words:
        end_pos = len(word)
        for start_pos in range(0, end_pos):
            suffixes.append(word[start_pos:end_pos])
    suffixes = ' '.join(suffixes)
    return suffixes
