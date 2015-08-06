"""
Main system controller
Initialises the data provider(s) and client-server interface(s) requested and
manages the main system event loop.
"""
import asyncio
from concurrent.futures import FIRST_COMPLETED, CancelledError
import urllib.parse

import oce.logger

logger = oce.logger.getLogger(__name__)

# ====================
# Providers/Interfaces
# ====================
import oce.config
import oce.providers
import oce.interfaces

# Parse from configuration file and prepare for instantiation
provider_classes = {}
for provider, details in oce.config.provider_classes.items():
    provider_classes[provider] = getattr(oce.providers, details['class'])

interface_classes = {}
for interface, details in oce.config.interface_classes.items():
    interface_classes[interface] = getattr(oce.interfaces, details['class'])

# ====================

import oce.langid
import oce.exceptions


def execute(**kwargs):
    """
    Initialises the controller and runs the main system loop until a shutdown
    is requested by a client.
    """
    actor = Act(**kwargs)
    loop = asyncio.get_event_loop()
    system_loop = loop.create_task(actor.run_controller())
    loop.run_forever()
    # === No processing occurs past this point until the loop stops ===

    # If the loop stopped, it's probably because someone requested a shutdown
    # or restart.  Clean up the controller and let the main script know what
    # happened.
    loop_exception = system_loop.exception()
    if loop_exception is not None:
        loop.run_until_complete(actor.shutdown())
        loop.close()
        raise loop_exception


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
        except oce.exceptions.CustomError as e:
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
        logger.info("=== Controller Initialisation ===")

        # Bring up data providers and server interfaces
        self.provider = None
        self.servers = []
        for key, value in kwargs.items():
            if value is None:
                # The user did not specify this provider/interface as a server
                # parameter, and its default settings have been disabled.
                continue
            if key in provider_classes.keys():
                if self.provider is None:
                    self.provider = provider_classes[key](value)
                else:
                    raise oce.exceptions.CustomError(
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
                raise oce.exceptions.CustomError(
                    "Invalid provider/interface: '{}'".format(key)
                )

        # Make sure they're up
        if self.provider is None:
            raise oce.exceptions.CustomError(
                "No data provider specified."
            )
        if len(self.servers) == 0:
            raise oce.exceptions.CustomError(
                "No interfaces specified."
            )

        # Lang ID module
        self.langid = oce.langid.LangIDController()

        # Client list - Servers will register their clients with us as they come
        self.clients = []
        # And when they do, this future will get resolved and recreated.
        self.clients_changed = asyncio.Future()
        # So that we can watch them for input
        # This is a list of tuples: (ClientInterface, Future)
        self.client_watch = []

    @asyncio.coroutine
    def shutdown(self):
        logger.info("Shutting down client watchers...")
        for x in self.client_watch:
            # The client watchers are coroutines
            x[1].cancel()
            yield from x[1]

        logger.info("Shutting down interfaces...")
        for server in self.servers:
            # The connection manager uses coroutines
            yield from server.shutdown()
        self.servers = []

        logger.info("Shutting down data provider...")
        self.provider.shutdown()
        self.provider = None

        logger.info("Shutting down langid module...")
        self.langid.shutdown()
        self.langid = None

    # ----------
    # Event Loop
    # ----------
    @asyncio.coroutine
    def run_controller(self):
        # N.B.: If Act was instantiated from an interactive console,
        # note that KeyboardInterrupt will drop back to a prompt
        # but NOT fully cancel the current iteration of do_loop() --
        # Old watchers will remain active, which might cause repeated
        #  operations and other subtle bugs.
        try:
            while True:
                yield from self.iterate_controller()
        except (oce.exceptions.RestartInterrupt,
                oce.exceptions.ShutdownInterrupt):
            asyncio.get_event_loop().stop()
            raise

    @asyncio.coroutine
    def iterate_controller(self):
        """
        In each iteration of the loop, we:

          1) Watch all registered clients, grabbing the first bit(s) of input to
             come through.  If any new clients are registered, restart the
             loop to include them too.
          2) Process the input and send it back to the client

        The beauty of coroutines is that we are guaranteed synchronous
        operation until we `yield from`, which blocks until something does
        happen (which prevents our pseudo-infinite loop above from chewing up
        resources)
        """

        # Watch new clients, stop watching dropped clients.
        # self.client_watch is a list of tuples (ClientInterface, Future)
        # that will be updated to represent all watched clients for this
        # iteration of the loop.
        watched_clients = []
        watched_client_futures = []
        for x in self.client_watch:
            if x[0] not in self.clients:
                # Goodbye
                x[1].cancel()
                yield from x[1]
                continue
            watched_clients.append(x[0])
            watched_client_futures.append(x[1])

        unwatched_clients = [client for client in self.clients
                             if client not in watched_clients]
        for client in unwatched_clients:
            # Hello
            watched_clients.append(client)
            watched_client_futures.append(
                asyncio.async(self._watch_client(client))
            )

        self.client_watch = [(watched_clients[x], watched_client_futures[x])
                             for x in range(len(watched_clients))]

        # Add the watcher for new/lost clients
        # On completion, this future will return True.
        # self.clients_changed will also be in the list of done tasks.
        watched_client_futures.append(self.clients_changed)

        # Begin the watch
        shutdown_this_watch = False
        restart_this_watch = False
        logger.debug(
            "Watcher: Watch begun. {} registered client(s).".format(
                len(watched_clients)
            )
        )
        client_watcher = asyncio.wait(watched_client_futures,
                                      return_when=FIRST_COMPLETED)
        done, _ = yield from client_watcher

        # Now deal with the ones which completed.
        # We are NOT guaranteed to have only one completed task here,
        # and we are NOT guaranteed that pending futures will stay
        # incomplete before the watch ends.
        for task in done:
            if task == self.clients_changed:
                logger.debug(
                    "Watcher: Clients changed. "
                    "Now have {} client(s).".format(
                        len(self.clients)
                    )
                )
                self.clients_changed = asyncio.Future()
            else:
                client, request = task.result()
                logger.debug(
                    "Watcher: Received client request: {}".format(
                        str(request)[0:80]
                    )
                )
                # Remove the watch here; a new future will be generated for
                # this client by the next iteration of the loop
                self.client_watch.remove((client, task))

                # If the client wanted a shutdown or restart, hold the request
                # until the end of the watch
                try:
                    return_message = self.exec_command(request)
                    yield from client.put_output_async(return_message)
                except oce.exceptions.ShutdownInterrupt:
                    shutdown_this_watch = True
                except oce.exceptions.RestartInterrupt:
                    restart_this_watch = True

        logger.debug(
            "Watcher: Watch ended."
        )

        if shutdown_this_watch:
            raise oce.exceptions.ShutdownInterrupt
        elif restart_this_watch:
            raise oce.exceptions.RestartInterrupt

    # ---------------------------
    # Client interface management
    # ---------------------------
    def register_client(self, client):
        self.clients.append(client)
        if not self.clients_changed.done():
            self.clients_changed.set_result(True)

    def deregister_client(self, client):
        self.clients.remove(client)
        if not self.clients_changed.done():
            self.clients_changed.set_result(True)

    @asyncio.coroutine
    def _watch_client(self, client):
        """
        Resolves the given future when the specified client provides some input.

        The future will contain a reference to the client as well, so we know
        exactly who gave us the input.
        (We wouldn't get this information if we were waiting only on each
        client's bare get_input_async())
        """
        try:
            message = yield from client.get_input_async()
            return client, message
        except CancelledError:
            logger.debug(
                "_watch_client cancelled: We either lost the client or are "
                "shutting down."
            )

    # ========
    # Commands
    # ========
    def exec_command(self, request):
        """
        Perform a requested command return the results as an object suitable for
        the client
        """

        # By delegating it to our lovely helper functions
        command = request['command']
        return_message = {}
        if hasattr(self, 'exec_' + command):
            command_fn = getattr(self, 'exec_' + command)
            results = command_fn(request)
        else:
            logger.warning("Invalid input from client.")
            results = "error"

        return {
            'command': command,
            'data': results
        }

    def exec_view(self, request):
        # Requested records with ID within specified range
        # Echoes target to the client (for asynchronous message handling)
        # TODO: This echo might not be necessary once the client starts using
        # promises.
        records = self.provider.fetch_records(request['start'], request['end'])
        if 'record' not in request.keys():
            request['record'] = request['start']
        return {
            'results': records,
            'record': request['record']
        }

    def exec_meta(self, _):
        total = self.provider.fetch_total()
        tags = self.provider.fetch_tags()

        return {
            'total': total,
            'tags': tags
        }

    def exec_update(self, request):
        return self.provider.update_record(request['rowid'],
                                           request['field'],
                                           request['value'])

    def exec_search(self, request):
        # Start by URL decoding
        params = urllib.parse.parse_qs(request['query'])
        query = params['s'][0]
        page = int(params['p'][0])
        limit = request['perpage']
        offset = (page - 1) * limit

        return self.provider.fetch_search_results(query, offset, limit)

    def exec_literal_query(self, request):
        limit = 0
        if "limit" in request.keys():
            limit = request["limit"]
        return self.provider.execute_literal(request['query'], limit=limit)

    def exec_drop(self, request):
        return self.provider.execute_drop(request['target'])

    def exec_recreate(self, request):
        return self.provider.execute_recreate(request['target'])

    @langid_function
    def exec_langid(self, request):
        """
        High-level manager for running language detection on a given record
        """
        record = self.provider.fetch_record(request['rowid'])

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
    def exec_retrain(self, _):
        """
        High-level manager for retraining the language detection classifier
        """
        # Get all the currently labelled records from the corpus, send them over
        # to the feature extractor
        labelled = self.provider.fetch_search_results('has:language', 0, 0)
        raw_data = labelled['results']
        # Normalise case + sort + save language labels in case it wasn't done
        # earlier.
        # TODO: Move this to a dedicate DB check function
        # for i, datum in enumerate(raw_data):
        #     normalised = oce.providers.util.langid_normalise_language(
        #         datum['language'])
        #     if normalised != datum['language']:
        #         self.provider.update_record(datum['rowid'], 'language',
        #                                     normalised)
        #     raw_data[i]['language'] = normalised
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
        labelled = self.provider.fetch_search_results('has:language', 0, 0)
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

    def exec_motd(self, _):
        """
        Return the motd to an motd-capable interface.
        """
        with open(oce.config.motd_file, 'r') as f:
            motd = f.read()
        return motd

    def exec_restart(self, _):
        """
        We're within Act's looping mechanism -- Raise the interrupt to drop out
        of the loop
        """
        raise oce.exceptions.RestartInterrupt

    def exec_shutdown(self, _):
        """
        Same as restart, but we're shutting down now
        """
        raise oce.exceptions.ShutdownInterrupt

    def exec_debug(self, _):
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
                "Could not load 'readline' module (probably on Win32): Tab "
                "completion will not work.")

        import code

        namespace = dict(globals(), **locals())
        code.interact(local=namespace)

    # --------------
    # Debug commands
    # --------------

    def features_of_record(self, rowid):
        record = self.provider.fetch_record(rowid)
        features = self.langid.extract_features(record['content'])
        return features
