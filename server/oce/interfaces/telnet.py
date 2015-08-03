"""
A simple TCP client-server interface.
"""
import asyncio
from concurrent.futures import CancelledError, FIRST_COMPLETED
import socket

import oce.logger

logger = oce.logger.getLogger(__name__)

from oce.interfaces.template import ServerInterface, ClientInterface


class TelnetServer(ServerInterface):
    def __init__(self, port, register_client, deregister_client):
        super().__init__(port, register_client, deregister_client)
        self.port = port
        self.register_client = register_client
        self.deregister_client = deregister_client

        self.server = asyncio.start_server(self._new_client_handler,
                                           host=None,
                                           port=port)

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))  # Google public DNS server
        self.local_ip = s.getsockname()[0]

        self.handler_list = []
        self.client_list = []

        logger.info(
            "Telnet server starting on {}, port {}.".format(self.local_ip,
                                                            self.port)
        )
        self.server = asyncio.get_event_loop().run_until_complete(self.server)

    @asyncio.coroutine
    def shutdown(self):
        """
        A coroutine that gracefully destroys the server
        """
        logger.info("Shutting down telnet server...")
        if len(self.client_list) > 0:
            logger.info("Kicking connected telnet clients...")
            for client in self.client_list:
                yield from client.close()

        # The handlers in handler_list only complete once their clients are
        # completely closed and deregistered.
        if len(self.handler_list) > 0:
            yield from asyncio.wait(self.handler_list)

        self.server.close()
        yield from self.server.wait_closed()
        logger.info("Telnet server shutdown complete.")

    @asyncio.coroutine
    def _new_client_handler(self, reader, writer):
        handler = asyncio.async(self._new_client_worker(reader, writer))
        self.handler_list.append(handler)
        yield from asyncio.wait_for(handler, None)

    @asyncio.coroutine
    def _new_client_worker(self, reader, writer):
        client = TelnetClient(reader, writer)
        self.client_list.append(client)
        self.register_client(client)
        yield from client.communicate_until_closed()
        self.deregister_client(client)
        self.client_list.remove(client)


class TelnetClient(ClientInterface):
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.remote_ip = writer.get_extra_info('peername')[0]

        self.input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()

    @asyncio.coroutine
    def close(self):
        """
        A coroutine that gracefully kicks the client
        """
        self.writer.close()

    @asyncio.coroutine
    def get_input_async(self):
        """
        A coroutine that returns the next message from the client
        The message must be a Dictionary that at least specifies a command for
        the controller.
        """
        # {
        #     'command': command,
        #     'other_params': other_params
        # }
        msg = yield from self.input_queue.get()
        # return msg
        return {'command': 'view', 'start': '12', 'end': '12', 'record': '12'}

    @asyncio.coroutine
    def put_output_async(self, msg):
        """
        A coroutine that sends the specified message to the client
        The message will be a Dictionary that echoes the client's command and
        sends the results as a sub-item
        """
        # {
        #     'command': command,
        #     'data': results
        # }
        yield from self.output_queue.put(msg)

    @asyncio.coroutine
    def communicate_until_closed(self):
        logger.info("[{}] New telnet client.".format(self.remote_ip))

        communication_tasks = [asyncio.async(self._receive_to_queue()),
                               asyncio.async(self._send_from_queue())]
        done, pending = yield from asyncio.wait(communication_tasks,
                                                return_when=FIRST_COMPLETED)

        logger.info(
            "[{}] Cleaning up client...".format(self.remote_ip)
        )

        for task in done:
            e = task.exception()
            if isinstance(e, Exception):
                # If any of our tasks threw an exception, re-raise it instead of
                # failing silently.
                raise e

        # Cancel any hangers-on (viz., _send_from_queue())
        for task in pending:
            task.cancel()
            yield from task

        logger.info("[{}] Cleanup complete.".format(self.remote_ip))

    @asyncio.coroutine
    def _receive_to_queue(self):
        try:
            while True:
                msg = yield from self.reader.readline()

                # If the EOF was received and the internal buffer is empty,
                # return an empty bytes object.
                if msg == b'':
                    logger.info(
                        "[{}] Client connection closed.".format(
                            self.remote_ip)
                    )
                    break

                yield from self.input_queue.put(msg)
                logger.info("[{}] [RECV] {}".format(
                    self.remote_ip,
                    msg)
                )
        except CancelledError:
            logger.debug(
                "[{}] CancelledError on receiver -- "
                "Should not be happening.".format(self.remote_ip)
            )

    @asyncio.coroutine
    def _send_from_queue(self):
        try:
            while True:
                msg = yield from self.output_queue.get()
                msg = str(msg)
                msg_preview = msg[0:80]
                # msg = base64.b64encode(zlib.compress(msg.encode())).decode()

                # if not self.websocket.open:
                #     logger.error(
                #         "[{}] Send error: Socket closed unexpectedly.".format(
                #             self.websocket.remote_ip))
                #     break
                self.writer.write(msg.encode())
                yield from self.writer.drain()
                logger.info("[{}] [SEND] {}...".format(
                    self.remote_ip,
                    msg_preview)
                )
        except CancelledError:
            logger.debug("[{}] Cancelling sender...".format(
                self.remote_ip))
