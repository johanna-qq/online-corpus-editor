# Online Corpus Editor: Server (Re-)Loader

import importlib
import sys

import oce.logger

logger = oce.logger.getLogger(__name__)

def init(sqlite=None, ws=None):
    """
    Starts up the server with the given parameters.
    """

    # We've delayed importing oce.services because it will pull in almost all
    # the system components, which can take a while; NLTK is particularly
    # expensive on first load.
    import oce.services

    oce.services.init(sqlite=sqlite, ws=ws)


def reload():
    """
    Dynamically reloads all system components in the given namespaces.

    Components deepest within the hierarchy are reloaded first,
    so subpackages that use the 'from ... import ...' syntax in __init__.py
    properly pick up any changes to their components.

    Anything in the priority_list is reloaded immediately, in the given order;
    the onus is on the user to ensure that dependencies are properly
    satisfied.
    """
    priority_list = [
        "oce.config"
    ]

    name_list = [
        "oce"
    ]

    to_reload = []

    for module in priority_list:
        if module in sys.modules.keys():
            logger.info("Reloading module - " + module)
            importlib.reload(sys.modules[module])

    for module in sys.modules.keys():
        if module in priority_list:
            continue
        for name in name_list:
            if module.startswith(name):
                to_reload.append(module)

    to_reload.sort(key=hierarchy_key, reverse=True)

    for module in to_reload:
        logger.info("Reloading module - " + module)
        importlib.reload(sys.modules[module])


def hierarchy_key(module_name):
    return module_name.count(".")
