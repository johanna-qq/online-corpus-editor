# Online Corpus Editor
# Language Identification: Configuration

# ==============
# System Options
# ==============

# Debug mode
debug_mode = False

# ------------------------
# Providers and Interfaces
# ------------------------
# The main script will parse these to allow the user to override them when
# starting the system.
# The system will attempt to use the defaults specified ('default_source' for
# providers, 'default_port' for interfaces) if the user does not pass any
# options to the main script; set these default options to None to disable them.

# Data providers:
# These modules manage a connection to the database that the corpus is stored
# in.  Only one should be active at any given time.
# Classes should be accessible as 'oce.providers.<class>'
provider_classes = {
    'sqlite': {
        'class': 'SQLiteProvider',
        'default_source': 'data/sge_tweets.db',
        'option_help': 'The path to the SQLite database file to use.'
    }
}

# Client-server Interfaces:
# These modules manage client connections to the system.  Multiple interfaces
# can be active at the same time.
# Classes should be accessible as 'oce.interfaces.<class>'
interface_classes = {
    'ws': {
        'class': 'WebsocketServer',
        'default_port': 8081,
        'option_help': 'The port to run the Websocket server on.'
    }
}

# ===============
# Corpus Database
# ===============

# Name of the base table in the corpus database
# From here, data providers may also expect to find:
#   <main_table>_fts    - Full-text search table
#   <main_table>_count  - Count of the total number of records in the corpus
#   <main_table>_tags   - User tags used
main_table = "tweets"

# =======================
# Language Identification
# =======================

# NLTK classifier model to use
default_model = "maxent"

# File to save the trained classifier to between server sessions
default_trained_file = "data/" + default_model + "-trained.pickle"

# PyEnchant Personal Word List file(s) for Singapore English
# Each file contains words (one per line) to identify as Singapore
# English tokens
sge_chinese_derived_words = ["data/sge-chinese-derived-discourse-particles.txt",
                             "data/sge-chinese-derived-common-words.txt"]
sge_malay_derived_words = ["data/sge-malay-derived-discourse-particles.txt",
                           "data/sge-malay-derived-common-words.txt"]
sge_words = ["data/sge-discourse-particles.txt",
             "data/sge-common-words.txt"]


