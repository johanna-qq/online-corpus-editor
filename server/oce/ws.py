# Deals with WebSocket-related operations

import asyncio
from concurrent.futures import FIRST_COMPLETED, CancelledError
import json
import socket
import websockets
from websockets.server import WebSocketServerProtocol
import zlib
import base64

import oce.logger
import oce.util

logger = oce.logger.getLogger(__name__)


class Conn:
    def __init__(self, port, processor_fn):
        """
        Prepares a new connection manager for handling WebSocket connections.
        :param port:
        :param processor_fn: Function to process incoming client messages.
        Should take the raw incoming message and return raw output for the
        client.
        :return:
        """
        # We're going to jury-rig a new class that inherits from
        # websockets.server.WebSocketServerProtocol so that we can save the
        # remote IP address of incoming connections.
        class CustomWebSocketServerProtocol(WebSocketServerProtocol):
            def connection_made(self, transport):
                self.remote_ip = transport.get_extra_info('peername')[0]
                super().connection_made(transport)

        # This just sets the server options; the server itself is only
        # available after .start_server() runs it via the event loop
        self.server = websockets.serve(self.client_handler_wrapper,
                                       host=None,
                                       port=port,
                                       klass=CustomWebSocketServerProtocol)
        self.port = port
        self.processor_fn = processor_fn

        # Small hack to try to get a usable local IP address
        # (Connecting to a UDP address doesn't send packets)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))  # Google public DNS server
        self.local_ip = s.getsockname()[0]
        self.client_list = []

        self.handlers = []
        self.do_restart = False
        self.do_shutdown = False
        return

    def start_server(self):
        logger.info("Server starting on {}, port {}.".format(self.local_ip,
                                                             self.port))
        self.server = asyncio.get_event_loop().run_until_complete(self.server)
        asyncio.get_event_loop().run_forever()
        # If we got past the last line, the server went down.

        if self.do_restart:
            raise oce.util.RestartInterrupt
        if self.do_shutdown:
            raise oce.util.ShutdownInterrupt
        return

    @asyncio.coroutine
    def shutdown(self):
        # Kick all clients
        if len(self.handlers) > 0:
            logger.info("Kicking connected clients...")
            for task in self.handlers:
                task.cancel()
            yield from asyncio.wait(self.handlers)

        logger.info("Shutting down WebSocket server...")
        self.server.close()
        yield from self.server.wait_closed()

    @asyncio.coroutine
    def client_handler_wrapper(self, websocket, path):
        """
        Wraps client_handler in a Task so that we can cleanly shut the server
        down when necessary.  path is passed as an argument by the websockets
        module, so we accept it here even though we don't use it.
        :param websocket:
        :param path:
        :return:
        """
        handler_task = asyncio.async(self.client_handler(websocket))
        self.handlers.append(handler_task)
        try:
            # Block until we get an error.
            yield from handler_task
        except CancelledError:
            handler_task.cancel()
            yield from handler_task
        except oce.util.RestartInterrupt:
            # We cannot propagate exceptions out of this handler... Try to
            # handle it here.
            self.do_restart = True
            asyncio.get_event_loop().stop()
        except oce.util.ShutdownInterrupt:
            self.do_shutdown = True
            asyncio.get_event_loop().stop()

    @asyncio.coroutine
    def client_handler(self, websocket):
        """
        Called by the Task wrapper above whenever a new client connects to the
        server.
        :param websocket: The client's socket
        :return:
        """
        self.client_list.append(websocket)

        logger.info('[{}] New client.'.format(websocket.remote_ip))

        # Instantiate messaging queues
        # Per client, NOT per instance
        in_queue = asyncio.Queue()
        out_queue = asyncio.Queue()

        # Bring up recv/send handling coroutines
        tasks = [asyncio.async(self.receiver(websocket, in_queue)),
                 asyncio.async(self.sender(websocket, out_queue)),
                 asyncio.async(
                     self.processor(websocket, in_queue, out_queue))]

        # Keep processing until one of the handlers returns
        # (E.g., the client closes the connection)
        # We wrap this in an outer Task so that we can call for all clients
        # to be cancelled externally.
        client_task = asyncio.wait(tasks, return_when=FIRST_COMPLETED)

        # We might also be forcibly cancelled by the server -- In which case,
        #  mark all our tasks as pending and let them end themselves.
        try:
            done, pending = yield from client_task
        except CancelledError:
            done = []
            pending = tasks

        logger.info("[{}] Cleaning up client.".format(websocket.remote_ip))

        do_restart = False
        do_shutdown = False
        for task in done:
            e = task.exception()
            if isinstance(e, oce.util.RestartInterrupt):
                # Prepare to trigger a restart
                do_restart = True
            elif isinstance(e, oce.util.ShutdownInterrupt):
                # Prepare for a shutdown
                do_shutdown = True
            elif isinstance(e, Exception):
                # If we couldn't handle the exception, re-raise it instead of
                # failing silently.
                raise e

        # Cancel all the other coroutines
        for task in pending:
            task.cancel()
        yield from asyncio.wait(pending)

        yield from websocket.close()
        self.client_list.remove(websocket)

        logger.info("[{}] Cleanup complete.".format(websocket.remote_ip))

        if do_restart:
            logger.info("[{}] Server restart requested.".format(
                websocket.remote_ip))
            raise oce.util.RestartInterrupt
        elif do_shutdown:
            logger.info("[{}] Server shutdown requested.".format(
                websocket.remote_ip))
            raise oce.util.ShutdownInterrupt
        return

    @asyncio.coroutine
    def receiver(self, websocket, in_queue):
        """
        Receives incoming messages to a websocket's input queue.
        """
        try:
            while True:
                msg = yield from websocket.recv()
                if msg is None:
                    logger.info("[{}] Client connection closed.".format(
                        websocket.remote_ip))
                    break
                yield from in_queue.put(msg)
                logger.info("[{}] [RECV] {}".format(websocket.remote_ip,
                                                    msg
                                                    .encode('ascii',
                                                            'xmlcharrefreplace')
                                                    .decode()))
        except CancelledError:
            logger.debug("[{}] Cancelling receiver...".format(
                websocket.remote_ip))
        return

    @asyncio.coroutine
    def sender(self, websocket, out_queue):
        """
        Sends messages out of a websocket's output queue
        """
        try:
            while True:
                msg = yield from out_queue.get()
                msg = json.dumps(msg)
                msg_preview = msg[0:80] \
                    .encode('ascii', 'xmlcharrefreplace').decode()
                msg = base64.b64encode(zlib.compress(msg.encode())).decode()

                if not websocket.open:
                    logger.error(
                        "[{}] Send error: Socket closed unexpectedly.".format(
                            websocket.remote_ip))
                    break
                yield from websocket.send(msg)
                logger.info("[{}] [SEND] {}...".format(websocket.remote_ip,
                                                       msg_preview))

        except CancelledError:
            logger.debug("[{}] Cancelling sender...".format(
                websocket.remote_ip))
        return

    @asyncio.coroutine
    def processor(self, websocket, in_queue, out_queue):
        """
        Processes messages that the receiver and sender put on the two
        queues, calling self.processor_fn (set on init) on client input.
        """
        try:
            while True:
                # Read from input queue
                client_input = yield from in_queue.get()

                # Attempt to decompress and parse JSON
                try:
                    client_input = json.loads(client_input)
                except ValueError:
                    logger.error("[{}] Bad input from client. (Could "
                                 "not parse JSON)".format(websocket.remote_ip))
                    # Leaving the loop kicks the client
                    return

                # Perform requested task and get results
                try:
                    client_output = self.processor_fn(client_input)
                except oce.util.RestartInterrupt:
                    logger.debug("[{}] Processor done: Client raised "
                                 "RestartInterrupt."
                                 .format(websocket.remote_ip))
                    raise
                except oce.util.ShutdownInterrupt:
                    logger.debug("[{}] Processor done: Client raised "
                                 "ShutdownInterrupt."
                                 .format(websocket.remote_ip))
                    raise

                yield from out_queue.put(client_output)
        except CancelledError:
            logger.debug("[{}] Cancelling processor...".format(
                websocket.remote_ip))
        return
