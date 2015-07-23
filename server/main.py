# Online Corpus Editor: Backend Server
# Zechy Wong, 19 May 2015 - 20 July 2015

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
import os
import sys

import oce
# This is a lazy-load; only the following are available:
# Methods: .init, .reload, .getLogger
# Classes: RestartInterrupt, ShutdownInterrupt, CustomError

# =============
# Configuration
# =============
default_ws_port = 8081
default_sqlite_db = 'data/sge_tweets.db'

# ==============
# Managing paths
# ==============
sys.path.insert(1, os.path.join(os.getcwd(), "lib"))

# ================
# Argument parsing
# ================
parser = argparse.ArgumentParser(
    description="Starts the backend server for the online corpus editor.",
    epilog="By default, a WebSocket server is started on port " +
           str(default_ws_port) + " using an SQLite DB located at '" +
           default_sqlite_db + "'.")
parser.add_argument('-ws',
                    default=default_ws_port,
                    metavar='WS_PORT',
                    help='The port to run the WebSocket server on.')
parser.add_argument('-sqlite',
                    default=default_sqlite_db,
                    metavar='SQLITE_DB',
                    help='The path to the SQLite database file to use.')
args = parser.parse_args()

# ====
# Init
# ====
logger = oce.getLogger(__name__)
logger.info("=== Server starting up ===")

# The server will reload itself if a user requests a restart.
# The only thing that won't be reloaded is this file.
quit_flag = False
while not quit_flag:
    try:
        oce.init(sqlite=args.sqlite, ws=args.ws)
    except oce.RestartInterrupt:
        logger.info("=== Server restarting ===")
        oce.reload()
        continue
    except oce.ShutdownInterrupt:
        logger.info("=== Server shutting down ===")
    except Exception as e:
        logger.error("=== Server Error ===")
        raise
