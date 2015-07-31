# Online Corpus Editor
# Language Identification: Configuration

# ==============
# System Options
# ==============


# ---------
# Databases
# ---------

# Name of the base table in the corpus database
# From here, data providers may also expect to find:
#   <main_table>_fts    - Full-text search table
#   <main_table>_count  - Count of the total number of records in the corpus
#   <main_table>_tags   - User tags used
main_table = "tweets"

# -----------
# Development
# -----------

# Debug mode
debug_mode = False

# -----------------------
# Language Identification
# -----------------------

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


