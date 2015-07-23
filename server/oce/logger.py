# Online Corpus Editor
# Server logger configuration

import datetime
import logging

# === Top-level Config ===
from oce.config import log_level

def get_gmt8(timestamp):
    """
    Returns a struct_time for the given time in SGT (GMT+8)
    :param timestamp:
    :return:
    """
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.fromtimestamp(timestamp, tz=tz).timetuple()


def getLogger(name):
    return logging.getLogger(name)

# On import/reload, (re-)configure the root logger, which will propagate to
# subsequent logger calls
root_logger = logging.getLogger()
if log_level == "debug":
    root_logger.setLevel(logging.DEBUG)
else:
    root_logger.setLevel(logging.INFO)
root_logger.handlers = []

formatter = logging.Formatter(
    # "[%(asctime)s] [%(levelname)s:%(name)s] %(message)s"
    "[%(asctime)s] [%(levelname)s] %(message)s"
)
formatter.converter = get_gmt8
formatter.datefmt = '%Y-%m-%d %H:%M:%S'

console_handler = logging.StreamHandler()

console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# SQLAlchemy prints a lot of messages at the INFO level.
logging.getLogger('sqlalchemy').setLevel(logging.WARN)

# Websockets also prints a lot of messages (including the contents of every frame)
# at the DEBUG level.
logging.getLogger('websockets.protocol').setLevel(logging.INFO)