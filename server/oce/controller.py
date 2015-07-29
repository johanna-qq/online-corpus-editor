"""
Main system controller.

Will initialise the data provider(s) and client-server interface(s) requested,
and manage the main system event loop.
"""

# =============
# Configuration
# =============
import oce.providers

provider_classes = {
    'sqlite': oce.providers.SQLiteProvider
}

import oce.interfaces

interface_classes = {
    'ws': oce.interfaces.WebsocketServer
}

# =============

import asyncio
from concurrent.futures import FIRST_COMPLETED
import urllib.parse

import oce.ws
import oce.db
import oce.langid
import oce.logger
import oce.util

import oce.providers.util

logger = oce.logger.getLogger(__name__)


def init(**kwargs):
    """
    Initialises the controller and starts the main system loop.
    """
    actor = Act(**kwargs)
    actor.start_loop()
    # === No processing occurs past this point until the system loop stops ===


# Decorator
def langid_function(func):
    """
    Wraps functions that use the langid module with a try..except block that
    catches NLTK LookupErrors, among other things.
    :param func:
    :return:
    """

    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except LookupError as e:

            return {
                'error': True,
                'message': "Server returned a LookupError:\n" + str(e).strip()
            }
        except oce.util.CustomError as e:
            return {
                'error': True,
                'message': str(e).strip()
            }
        except Exception as e:
            # Better to return something than fail silently
            return {
                'error': True,
                'message': "Server returned an error:\n" + repr(e).strip()
            }

    return wrapped


class Act:  # Hurr hurr
    # ---------------------------
    # Initialisation and Shutdown
    # ---------------------------
    def __init__(self, **kwargs):
        """
        **kwargs should specify exactly one provider class and at least one
        interface class.
        """
        logger.info("Initialising system components...")

        # Bring up data providers and server interfaces
        self.provider = None
        self.servers = []
        for key, value in kwargs.items():
            if key in provider_classes.keys():
                if self.provider is None:
                    self.provider = provider_classes[key](value)
                else:
                    raise oce.util.CustomError(
                        "More than one data provider specified."
                    )
            elif key in interface_classes.keys():
                # Interfaces also need to be passed our client de-/registration
                # functions
                server = interface_classes[key](value,
                                                self.register_client,
                                                self.deregister_client)
                self.servers.append(server)
            else:
                raise oce.util.CustomError(
                    "Invalid provider/interface: '{}'".format(key)
                )
        if self.provider is None:
            raise oce.util.CustomError(
                "No data provider specified."
            )
        if len(self.servers) == 0:
            raise oce.util.CustomError(
                "No interfaces specified."
            )

        # Client list - Servers will register their clients with us as they come
        self.clients = []
        # And when they do, this future will get resolved and recreated.
        self.clients_changed = asyncio.Future()

        # If any of our methods set this to False, the system gets punted back
        # up to the main script. We should also raise a corresponding interrupt
        # if it was a user-requested restart or shutdown.
        self.stop_loop = False

    def start_loop(self):
        loop = asyncio.get_event_loop()
        while not self.stop_loop:
            loop.run_until_complete(self.do_loop())

    @asyncio.coroutine
    def do_loop(self):
        """
        In each iteration of the loop, we:

          1) Watch all registered clients, grabbing the first bit of input to
             come through.  If any new clients are registered, restart the
             loop to include them too.
          2) Process the input and send it back to the client
          3) Set self.stop_loop if we we're done

        The beauty of coroutines is that we are guaranteed synchronous setup
        until we `yield from`, which blocks until something does happen (which
        prevents our pseudo-infinite loop above from chewing up resources)
        """

        sub_watch_clients = []
        # Schedule the client input watchers
        for client in self.clients:
            future = asyncio.Future()
            asyncio.async(self._watch_client(future, client))
            sub_watch_clients.append(future)
        # And the watcher for new/lost clients
        self.clients_changed = asyncio.Future()
        sub_watch_clients.append(self.clients_changed)
        watch_clients = asyncio.wait(sub_watch_clients,
                                     return_when=FIRST_COMPLETED)

        done = []
        pending = []
        try:
            done, pending = yield from watch_clients
        finally:
            for task in done:
                print(task)
                print(task == self.clients_changed)
                print(task.result())
                print("-----")

    def shutdown(self):

        print("Shutting down connection manager...")
        # The connection manager uses coroutines
        asyncio.get_event_loop().run_until_complete(self.conn.shutdown())
        self.conn = None

        print("Shutting down DB manager...")
        self.db.shutdown()
        self.db = None

        print("Shutting down langid module...")
        self.langid.shutdown()
        self.langid = None
        return

    # ---------------------------
    # Client interface management
    # ---------------------------
    def register_client(self, client):
        self.clients.append(client)
        self.clients_changed.set_result(True)

    def deregister_client(self, client):
        self.clients.remove(client)
        self.clients_changed.set_result(True)

    @asyncio.coroutine
    def _watch_client(self, future, client):
        """
        Resolves the given future when the specified client provides some input.

        The future will contain a reference to the client as well, so we know
        exactly who gave us the input.
        (We wouldn't get this information if we were waiting only on each
        client's bare get_input_async())
        """
        message = yield from client.get_input_async()
        future.set_result((client, message))

    # --------
    # Commands
    # --------
    def exec_command(self, request):
        """
        Perform a requested command return the results as an object suitable for
        the client
        :param request:
        :return:
        """

        # By delegating it to our lovely helper functions
        command = request['command']
        command_fn = getattr(self, 'exec_' + command)
        results = command_fn(request)

        return {
            'command': command,
            'data': results
        }

    def exec_view(self, request):
        # Requested records with ID within specified range
        # Echoes target to the client (for asynchronous message handling)
        records = self.db.fetch_records(request['start'], request['end'])

        return {
            'results': records,
            'record': request['record']
        }

    def exec_meta(self, request):
        total = self.db.fetch_total()
        tags = self.db.fetch_tags()

        return {
            'total': total,
            'tags': tags
        }

    def exec_update(self, request):
        return self.db.update_record(request['rowid'], request['field'],
                                     request['value'])

    def exec_search(self, request):
        # Start by URL decoding
        params = urllib.parse.parse_qs(request['query'])
        query = params['s'][0]
        page = int(params['p'][0])
        limit = request['perpage']
        offset = (page - 1) * limit

        return self.db.fetch_search_results(query, offset, limit)

    @langid_function
    def exec_langid(self, request):
        """
        High-level manager for running language detection on a given record
        :param rowid:
        :return:
        """
        record = self.db.fetch_record(request['rowid'])

        # Do a quick sanity check on the classifier so that we can
        # exec_retrain if necessary.
        if not self.langid.check_classifier():
            if not self.exec_retrain():
                # Something's wrong with the system.
                return "error"

        self.langid.debug(record['content'])
        suggested = self.langid.suggest_language(record['content'])
        return [record['content'], suggested]

    @langid_function
    def exec_retrain(self, request=None):
        """
        High-level manager for retraining the language detection classifier
        :param request:
        :return:
        """
        # Get all the currently labelled records from the corpus, send them over
        # to the feature extractor
        labelled = self.db.fetch_search_results('has:language', 0, 0)
        raw_data = labelled['results']
        # Normalise case + sort + save language labels in case it wasn't done
        # earlier.
        for i, datum in enumerate(raw_data):
            normalised = oce.providers.util.langid_normalise_language(
                datum['language'])
            if normalised != datum['language']:
                self.db.update_record(datum['rowid'], 'language', normalised)
            raw_data[i]['language'] = normalised
        labelled_data = self.langid.prepare_labelled_data(raw_data)
        training_set = [(self.langid.extract_features(s), l)
                        for (s, l) in labelled_data]
        self.langid.train_classifier(training_set)
        if self.langid.check_classifier():
            # We got *something* usable as a classifier
            return True
        else:
            # Something failed
            return False

    @langid_function
    def exec_find_features(self, feature_name):
        """
        Finds all language-tagged records in the corpus which match a certain
        classifier feature
        """
        labelled = self.db.fetch_search_results('has:language', 0, 0)
        raw_data = labelled['results']
        for datum in raw_data:
            if self.langid.extract_features(datum['content'])[feature_name]:
                logger.debug(
                    "Record {0} matches '{1}': {2}.\nLabel is {3}".format(
                        datum['rowid'],
                        feature_name,
                        datum['content'],
                        datum['language']
                    )
                )

    def exec_restart(self, request=None):
        """
        We're still within one of conn's coroutines -- Raise the interrupt
        and deal with it higher
        :param request:
        :return:
        """
        raise oce.util.RestartInterrupt

    def exec_shutdown(self, request=None):
        """
        Same as restart, but we're shutting down now
        """
        raise oce.util.ShutdownInterrupt

    def exec_debug(self, request=None):
        """
        Starts an interactive console on the current Act object for debugging.
        """
        import sys

        try:
            import readline
            import rlcompleter

            if sys.platform.startswith('darwin'):
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")
        except ImportError:
            # On Windows, probably
            print(
                "Could not load 'readline' module (probably on Win32): Tab completion will not work.")

        import code

        namespace = dict(globals(), **locals())
        code.interact(local=namespace)

    # --------------
    # Debug commands
    # --------------

    def features_of_record(self, rowid):
        record = self.db.fetch_record(rowid)
        features = self.langid.extract_features(record['content'])
        return features
