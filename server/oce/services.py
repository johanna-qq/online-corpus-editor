# Server functions

import asyncio
import urllib.parse

import oce.ws
import oce.db
import oce.langid

logger = oce.getLogger(__name__)


def init(sqlite=None, ws=None):
    actor = Act(sqlite, ws)
    actor.start_ws_server()


# Decorator
def langid_function(func):
    """
    Wraps functions that use the langid module with a try..except block that
    catches NLTK LookupErrors.
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
    def __init__(self, db_file, ws_port):
        logger.info("Initialising system components...")

        # Initialise DB connection
        self.db = oce.db.DB(db_file)

        # Run any ad hoc DB commands
        self.db.debug()

        # Initialise language detection module
        self.langid = oce.langid.LangIDController()

        # Initialise local WebSocket server on specified port
        self.conn = oce.ws.Conn(ws_port, self.exec_command)

        return

    def start_ws_server(self):
        try:
            self.conn.start_server()
        # --- Now running in asyncio event loop; no further processing here ---
        except (oce.util.RestartInterrupt, oce.util.ShutdownInterrupt):
            # The server went down.  Shutdown all system components, then raise
            # the exception to main so that the Act module itself can
            # be reloaded (if a restart was requested).
            self.shutdown()
            raise

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
        return self.db.fetch_meta()

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
            normalised = self.db.normalise_language(datum['language'])
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

    def exec_restart(self, request=None):
        """
        We're still within one of conn's coroutines -- Raise the interrupt
        and deal with it higher
        :param request:
        :return:
        """
        raise oce.RestartInterrupt

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
            print("Could not load 'readline' module (probably on Win32): Tab completion will not work.")

        import code

        namespace = dict(globals(), **locals())
        code.interact(local=namespace)
