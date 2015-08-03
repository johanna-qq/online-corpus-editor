"""
Manages the telnet parser
"""
import asyncio
from concurrent.futures import CancelledError, FIRST_COMPLETED

import textwrap

import oce.logger

logger = oce.logger.getLogger(__name__)

# === Command/Reply/Help Tables ===
# The command table maps the first word of the client input to a given
# command function.  The command functions are all methods of the
# TelnetParser class.
# Note: All the command functions should be coroutines.  Any value that they
# return will be sent to the server as a request.  If nothing needs to be
# sent to the server, have the function return None.
command_table = {
    # Client administration
    'exit': 'command_exit',
    'quit': 'command_exit',
    'motd': 'command_motd',
    'commands': 'command_commands',

    # Server administration
    'restart': 'command_restart',
    'shutdown': 'command_shutdown',

    # Data functions
    'meta': 'command_meta'
}
command_list = list(command_table.keys())
command_list.sort()

# The reply table maps the 'command' field of a reply from the server to a
# function that formats the rest of the reply for sending back to the client.
# Note: As above, all the formatting functions should be coroutines; to
# suppress output to the client, have the function return None.
format_table = {
    'default': 'format_raw',
    'motd': 'format_raw'
}

# The help table maps the names of commands to their help strings.
# When a user types 'help <key>', help_table[<key>] gets returned.
# The help strings should be actual Strings
# TODO: These will be in a separate file/db
# from telnet_help import help_table


class TelnetParser:
    def __init__(self, client_input, client_output, remote_ip):
        # The parser maintains its own input and output queues to deal with
        # commands that we don't need to query the server for.
        # We read client_input from TelnetClient and give parsed_input to the
        #  Controller.
        # We read raw_output from the Controller and format it for
        # client_output.
        self.client_input = client_input
        self.client_output = client_output
        self.remote_ip = remote_ip

        self.parsed_input = asyncio.Queue()
        self.raw_output = asyncio.Queue()

        self.textwrap = textwrap.TextWrapper()
        self.prompt = "> "

    @asyncio.coroutine
    def get_parsed(self):
        msg = yield from self.parsed_input.get()
        return msg

    @asyncio.coroutine
    def put_raw(self, msg):
        yield from self.raw_output.put(msg)

    @asyncio.coroutine
    def run_parser(self):
        # We're starting to communicate with the server; put in a preliminary
        # motd command.
        yield from self.client_input.put(b'motd\r\n')

        # Keep reading and processing client_input/raw_output
        communication_tasks = [asyncio.async(self._read_client_input()),
                               asyncio.async(self._read_server_output())]
        try:
            done, pending = yield from asyncio.wait(communication_tasks,
                                                    return_when=FIRST_COMPLETED)
        except CancelledError:
            logger.debug("[{}] Cancelling parser...".format(self.remote_ip))
            done = []
            pending = communication_tasks

        # If we're here, either the parser was cancelled or the client raised
        #  a TelnetExit
        for task in done:
            e = task.exception()
            if isinstance(e, Exception):
                raise e

        for task in pending:
            task.cancel()
            yield from task

    @asyncio.coroutine
    def _read_client_input(self):
        try:
            while True:
                msg = yield from self.client_input.get()
                # Msg is a byte string
                msg = msg.decode()
                yield from self.parse_client_input(msg)
        except CancelledError:
            logger.debug(
                "[{}] Cancelling parser's input loop...".format(
                    self.remote_ip)
            )

    @asyncio.coroutine
    def _read_server_output(self):
        try:
            while True:
                msg = yield from self.raw_output.get()
                yield from self.parse_server_output(msg)
        except CancelledError:
            logger.debug(
                "[{}] Cancelling parser's output loop...".format(
                    self.remote_ip
                )
            )

    @asyncio.coroutine
    def parse_client_input(self, msg):
        """
        Parses commands sent by the client and transforms them into the
        Dictionary format expected by the controller.

        If there is anything to send to the server, put it on self.parsed_input
        """
        command_array = msg.split()
        if len(command_array) == 0:
            yield from self.send_to_client('')
            return

        command_name = command_array.pop(0)
        command_fn = ''
        for command in command_list:
            if command.startswith(command_name):
                command_fn = command_table[command]
                break
        if command_fn == '':
            # We didn't find a match in the command table
            yield from self.send_to_client("Invalid command.")
            return

        if not hasattr(self, command_fn):
            # There's a problem with the command table
            logger.warning("Telnet command '{}' has an entry in the command "
                           "table, but does not have a corresponding "
                           "function defined.".format(command_fn))
            yield from self.send_to_client("Invalid command.")
            return

        request = yield from getattr(self, command_fn)(*command_array)
        if request is not None:
            # The command function gave us a request payload for the server.
            yield from self.parsed_input.put(request)

    @asyncio.coroutine
    def parse_server_output(self, msg):
        """
        Takes a Dictionary response from the controller and formats it in a
        readable way for the client.

        If there is anything to send back to the client, call send_to_client()
        on it.
        """

        command_name = msg['command']
        if command_name not in format_table.keys():
            logger.warning("Telnet command '{}' does not have an associated "
                           "formatting function.".format(command_name))
            logger.warning("Defaulting to showing raw server response.")
            command_name = 'default'

        format_fn = format_table[command_name]
        if not hasattr(self, format_fn):
            logger.warning(
                "Telnet command '{}' has an entry in the  formatting table, "
                "but does not have a corresponding function defined.".format(
                    command_name
                )
            )
            logger.warning("Defaulting to showing raw server response.")
            format_fn = format_table['default']

        formatted = yield from getattr(self, format_fn)(msg['data'])
        if formatted is not None:
            yield from self.send_to_client(formatted)

    @asyncio.coroutine
    def send_to_client(self, msg, prompt=True):
        """
        Sends an arbitrary message to the client.
        """
        # Wrap all output to the client
        msg_lines = msg.splitlines()
        msg_wrapped = ["\r\n".join(self.textwrap.wrap(line)) for line in
                       msg_lines]
        msg = "\r\n".join(msg_wrapped)

        # Leading and trailing newlines for non-empty messages
        if msg != '':
            msg = "\r\n{}\r\n\r\n".format(msg)

        if prompt:
            to_client = "{}{}".format(msg, self.prompt)
        else:
            to_client = msg
        yield from self.client_output.put(to_client)

    # === Command Functions ===
    @asyncio.coroutine
    def command_exit(self):
        raise TelnetExit

    @asyncio.coroutine
    def command_restart(self):
        request = {'command': 'restart'}
        yield from self.send_to_client("[Requesting server restart]",
                                       prompt=False)
        return request

    @asyncio.coroutine
    def command_shutdown(self):
        request = {'command': 'shutdown'}
        yield from self.send_to_client("[Requesting server shutdown]",
                                       prompt=False)
        return request

    @asyncio.coroutine
    def command_motd(self):
        request = {'command': 'motd'}
        return request

    @asyncio.coroutine
    def command_meta(self):
        request = {'command': 'meta'}
        return request

    @asyncio.coroutine
    def command_commands(self):
        # Todo: This should be nicer.
        data = "Commands:\r\n{}".format(" ".join(command_list))
        yield from self.send_to_client(data)

    # === Format Functions ===
    @asyncio.coroutine
    def format_raw(self, reply):
        return str(reply)


class TelnetExit(Exception):
    """
    When raised, the main telnet interface will know the client wants to exit
    """

    def __init__(self):
        self.value = "TelnetExit"

    def __str__(self):
        return repr(self.value)
