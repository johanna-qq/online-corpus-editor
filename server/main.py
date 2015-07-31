# Online Corpus Editor: Backend Server
# Zechy Wong, 19 May 2015 - 30 July 2015

"""
Dependencies
============
Python 3.4.3
WebSockets (https://pypi.python.org/pypi/websockets)
SQLAlchemy (https://pypi.python.org/pypi/SQLAlchemy/1.0.4)
SQLite with FTS support (https://sqlite.org/fts3.html)
 |- [Bundled] Windows DLL and Linux library with Enhanced Query Syntax
PyEnchant (https://pythonhosted.org/pyenchant/)
 |- Also see: https://github.com/rfk/pyenchant/issues/45
Numpy (http://www.numpy.org/)
NLTK (http://www.nltk.org/)
 |- Also use the NLTK downloader to install the following NLTK package(s):
     |- punkt

Recommended
===========
Megam (http://www.umiacs.umd.edu/~hal/megam/)
 |- [Bundled] Binaries for Windows, Linux and OS X
Hunspell Dictionaries
 |- [Bundled] Dictionaries for en_GB and en_US (http://wordlist.aspell.net/dicts/)
 |- [Bundled] Dictionary for ms_MY (From the LyX sources: http://www.lyx.org/)

NOTE: Bundled dependencies (in the 'lib' folder) will take precedence over
versions elsewhere on the system.
"""

import argparse
import importlib
import logging
import os
import sys

# =============
# Configuration
# =============
# The following interfaces/data providers will be initialised by default.
# To disable any of them, set the corresponding value below to None.
# I.e., default_<option> = None
default_ws_port = 8081
default_sqlite_db = 'data/sge_tweets.db'

# ===============
# Path management
# ===============
sys.path.insert(1, os.path.join(os.getcwd(), "lib"))

# ================
# Argument parsing
# ================
parser = argparse.ArgumentParser(
    description="Starts the backend system for the online corpus editor.",
    epilog="Default settings for data providers and client-server interfaces "
           "can be set in 'oce/config.py'.")

parser.add_argument('-ws',
                    default=default_ws_port,
                    metavar='WS_PORT',
                    help='The port to run the WebSocket server on.')
parser.add_argument('-sqlite',
                    default=default_sqlite_db,
                    metavar='SQLITE_DB',
                    help='The path to the SQLite database file to use.')

kwargs = vars(parser.parse_args())

# ====
# Init
# ====
quit_flag = False
while not quit_flag:

    print("\n=== Server starting up ===\n")

    # Start up the loader, which tracks imports past this point and marks them
    # for reloading when the server is restarted.
    # The only thing that won't be reloaded is this file.
    loader = importlib.import_module('oce.loader').Loader()

    exceptions = importlib.import_module('oce.exceptions')
    try:
        loader.init(**kwargs)
    except exceptions.RestartInterrupt:
        print("\n=== Restarting system ===\n")
        loader.unload()
        del loader
        # And loop around to recreate `loader` and reload the system
    except exceptions.ShutdownInterrupt:
        print("\n=== Shutting down system ===\n")
        quit_flag = True
    except Exception as e:
        print("\n<<< System Error >>>\n")
        raise
    else:
        # The server went down silently -- This shouldn't happen, but let's
        # log it and leave the system down (in case of infinite loops etc.)
        print("\n<<< Unexpected shutdown >>>\n")
        quit_flag = True
    finally:
        # Reset the logger so that any final log messages (from unexpected
        # errors, etc.) use the basic handler
        root_logger = logging.getLogger()
        root_logger.handlers = []
        logging.basicConfig()
