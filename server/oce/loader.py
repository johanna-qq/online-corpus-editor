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
    # Language ID
    "oce.langid.langid",
    "oce.langid.features",
    "oce.langid",
    # Main controller
    "oce.controller",
    # [Transitional]
    "oce.ws",
    "oce.db"
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

#
# def init(sqlite=None, ws=None):
#     """
#     Starts up the server with the given parameters.
#     """
#
#     # We've delayed importing the main module because it will pull in almost all
#     # the system components, which can take a while; NLTK is particularly
#     # expensive on first load.
#     import oce.controller
#
#     oce.controller.init(sqlite=sqlite, ws=ws)
#
#
# def load_package(load_order):
#     """
#     Loads a package by either importing or reloading the dependencies it
#     specifies (in order).
#     """
#     for module in load_order:
#         if module in sys.modules.keys():
#             print("reloading " + str(module))
#             importlib.reload(sys.modules[module])
#         else:
#             print("importing " + str(module))
#             importlib.import_module(module)
#
#
# def reload():
#     """
#     Dynamically reloads all system components in the given namespaces.
#
#     Components deepest within the hierarchy are reloaded first,
#     so subpackages that use the 'from ... import ...' syntax in __init__.py
#     properly pick up any changes to their components.
#
#     Anything in the priority_list is reloaded immediately, in the given order;
#     the onus is on the user to ensure that dependencies are properly
#     satisfied.
#     """
#     priority_list = [
#         "oce.config"
#     ]
#
#     name_list = [
#         "oce"
#     ]
#
#     to_reload = []
#
#     for module in priority_list:
#         if module in sys.modules.keys():
#             logger.info("Reloading module - " + module)
#             importlib.reload(sys.modules[module])
#
#     for module in sys.modules.keys():
#         if module in priority_list:
#             continue
#         for name in name_list:
#             if module.startswith(name):
#                 to_reload.append(module)
#
#     to_reload.sort(key=hierarchy_key, reverse=True)
#
#     for module in to_reload:
#         actual_module = sys.modules[module]
#         logger.info("Reloading module - " + module)
#         importlib.reload(sys.modules[module])
#         # Modules may specify additional post-processing to do in
#         # post_reload(), including re-reloading their submodules for proper
#         # dependency handling.
#         if hasattr(actual_module, 'post_reload'):
#             actual_module.post_reload()
#
#
# def hierarchy_key(module_name):
#     return module_name.count(".")
