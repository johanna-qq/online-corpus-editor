# Online Corpus Editor: Server (Re-)Loader

import importlib
import sys

import oce.logger

logger = oce.logger.getLogger(__name__)
load_order = [
    # General
    "oce.config",
    "oce.logger",
    "oce.util",
    # Data providers
    "oce.providers.util",
    "oce.providers.template",
    "oce.providers.sqlite",
    "oce.providers",
    # Interfaces
    "oce.interfaces.template",
    "oce.interfaces.websocket",
    "oce.interfaces",
    # Language ID
    "oce.langid.langid",
    "oce.langid.features",
    "oce.langid",
    # Main controller
    "oce.controller"
]
modules_loaded = False
controller_name = "oce.controller"


def init(*args, **kwargs):
    """
    Starts up the server with the given parameters.
    We wait till now to do the full load because some of the modules can
    take a while to initialise; NLTK is particularly expensive on first
    load.
    """
    global modules_loaded
    if not modules_loaded:
        load_modules()
        modules_loaded = True
    sys.modules[controller_name].init(*args, **kwargs)


def load_modules():
    """
    Loads the modules specified in load_order
    """
    for module in load_order:
        logger.debug("Importing module - " + module)
        importlib.import_module(module)


def reload():
    """
    Reloads all the modules specified in load_order
    """
    global modules_loaded
    for module in load_order:
        logger.info("Reloading module - " + module)
        importlib.reload(sys.modules[module])
        modules_loaded = True
    return
