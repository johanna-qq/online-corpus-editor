"""
Handles the loading/reloading of the entire backend system
(Experimental)
"""

import importlib
import sys

# Constant module names
logger_mod = 'oce.logger'
controller_mod = 'oce.controller'


class Loader:
    def __init__(self):
        """
        Starts tracking all external modules loaded past this point
        (Idea from http://pyunit.sourceforge.net/notes/reloading.html)
        """
        self.prev_modules = sys.modules.copy()
        self.logger = importlib.import_module(logger_mod).getLogger(__name__)
        self.logger.info("Loader: Now tracking new imports.")

    def init(self, *args, **kwargs):
        """
        Starts up the server with the given parameters.
        We wait till now to do the full load because some of the modules can
        take a while to initialise; NLTK is particularly expensive on first
        load.
        """
        importlib.import_module(controller_mod).init(*args, **kwargs)

    def shutdown(self):
        """
        Propagates a shutdown request from the main script into the controller
        """
        importlib.import_module(controller_mod).shutdown()

    def unload(self):
        """
        Removes all OCE modules and external dependencies from the import cache;
        They will be reloaded when next imported.
        """
        self.logger.info("Loader: Marking system modules for reload.")
        keep_modules = list(self.prev_modules.keys())
        current_modules = list(sys.modules.keys())
        for module in current_modules:
            if module not in keep_modules or module.startswith("oce"):
                self.logger.debug(
                    "Loader: Invalidating cached module -- {}".format(module)
                )
                del sys.modules[module]
