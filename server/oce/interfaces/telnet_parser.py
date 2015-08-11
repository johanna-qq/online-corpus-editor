"""
Manages the telnet parser
"""
import asyncio
from concurrent.futures import CancelledError, FIRST_COMPLETED

import re
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
    '!': 'command_repeat_last',
    'commands': 'command_commands',
    'motd': 'command_motd',
    'exit': 'command_exit',
    'quit': 'command_exit',

    # Server administration
    'restar': 'command_need_full',
    'restart': 'command_restart',
    'shutdow': 'command_need_full',
    'shutdown': 'command_shutdown',

    # Database functions
    'db': 'command_db_branch',

    # Debug
    'debugsleep': 'command_debugsleep'
}

# The reply table maps the 'command' field of a reply from the server to a
# function that formats the rest of the reply for sending back to the client.
# Note: As above, all the formatting functions should be coroutines; to
# suppress output to the client, have the function return None.
format_table = {
    'default': 'format_raw',
    'motd': 'format_raw',
    'db_get_config': 'format_db_get_config',
    'db_set_config': 'format_db_set_config',
    'literal_query': 'format_literal_query'
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

        # Stuff on parsed_input gets sent to the server
        self.parsed_input = asyncio.Queue()
        # Stuff on raw_output gets run through the formatter
        self.raw_output = asyncio.Queue()

        self.textwrap = textwrap.TextWrapper()

        # Client variables
        self.prompt = "> "
        self.last_command = ""
        self.config = {}

    @asyncio.coroutine
    def get_input_async(self):
        """
        Called by TelnetClient when the server wants input from us
        """
        msg = yield from self.parsed_input.get()
        return msg

    @asyncio.coroutine
    def put_output_async(self, msg):
        """
        Called by TelnetClient when the server wants to give us a reply
        """
        yield from self.raw_output.put(msg)

    @asyncio.coroutine
    def run_parser(self):
        # We're starting to communicate with the server; put in a preliminary
        # motd command.
        # yield from self.client_input.put(b'motd\r\n')
        yield from self.command_motd()

        # Keep reading and processing client_input/raw_output
        communication_tasks = [asyncio.async(self._read_client_input()),
                               asyncio.async(self._read_server_output())]
        try:
            yield from asyncio.wait(communication_tasks,
                                    return_when=FIRST_COMPLETED)
        except CancelledError:
            logger.debug("[{}] Cancelling parser...".format(self.remote_ip))

        # If we're here, either the parser was cancelled or the client raised
        # a TelnetExit
        got_exception = None
        for task in communication_tasks:
            if task.done():
                e = task.exception()
                if isinstance(e, Exception):
                    got_exception = e
            else:
                task.cancel()
                yield from task

        if got_exception is not None:
            raise got_exception

    @asyncio.coroutine
    def _read_client_input(self):
        try:
            while True:
                msg = yield from self.client_input.get()

                try:
                    # Msg is a byte string
                    msg = msg.decode()
                    yield from self.parse_client_input(command_table, msg)

                except UnicodeDecodeError:
                    # But it might contain undecodable characters
                    # (E.g., interrupts)
                    yield from self._handle_undecodable(msg)

        except CancelledError:
            logger.debug(
                "[{}] Cancelling parser's input loop...".format(
                    self.remote_ip)
            )

    @asyncio.coroutine
    def _read_server_output(self):
        task = None
        try:
            while True:
                task = asyncio.async(self.raw_output.get())
                msg = yield from task
                task = asyncio.async(self.parse_server_output(msg))
                yield from task

        except CancelledError:
            logger.debug(
                "[{}] Cancelling parser's output loop...".format(
                    self.remote_ip
                )
            )
            # Note: wait_for doesn't work here, for some reason.
            yield from asyncio.wait([task])

    @asyncio.coroutine
    def _handle_undecodable(self, msg):
        """
        If the client sends us something strange, see what we can do about it
        here.
        """
        if msg.startswith(b'\xff\xf4\xff\xfd\x06'):
            # Client sent a ^C; we should drop them.
            raise TelnetExit
        else:
            yield from self.send_to_client("Invalid command.")

    @asyncio.coroutine
    def send_to_client(self, msg, prompt=True):
        """
        Sends a message to the client, optionally displaying the prompt as well
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

    @asyncio.coroutine
    def send_to_server(self, request):
        """
        Sends a request payload to the server.
        """
        yield from self.parsed_input.put(request)

    @asyncio.coroutine
    def parse_client_input(self, fn_table, msg):
        """
        Parses commands sent by the client against the function table
        provided.
        """
        if not msg.startswith("!"):
            self.last_command = msg

        command_array = msg.split()
        if len(command_array) == 0:
            yield from self.send_to_client('')
            return

        fn_list = list(fn_table.keys())
        fn_list.sort()

        command_name = command_array.pop(0)
        command_fn = ''
        for command in fn_list:
            if command.startswith(command_name):
                command_fn = fn_table[command]
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

        yield from getattr(self, command_fn)(*command_array)

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

    # === Command Functions ===
    @asyncio.coroutine
    def command_repeat_last(self):
        """
        self.last_command is updated by self.parse_client_input
        """
        yield from self.parse_client_input(command_table, self.last_command)

    @asyncio.coroutine
    def command_commands(self):
        # Todo: This should be nicer.
        command_list = list(command_table.keys())
        command_list.sort()
        data = "Commands:\r\n{}".format(" ".join(command_list))
        yield from self.send_to_client(data)

    @asyncio.coroutine
    def command_motd(self):
        request = {'command': 'motd'}
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_exit(self):
        raise TelnetExit

    @asyncio.coroutine
    def command_need_full(self):
        yield from self.send_to_client("You need to type that command out in "
                                       "full.")

    @asyncio.coroutine
    def command_restart(self):
        request = {'command': 'restart'}
        yield from self.send_to_client("[Server restarting]",
                                       prompt=False)
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_shutdown(self):
        request = {'command': 'shutdown'}
        yield from self.send_to_client("[Server shutting down]",
                                       prompt=False)
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_db_branch(self, *args):
        """
        Branches off into various db operations.
        """
        branch_table = {
            # Provider admin
            'config': 'command_db_config',

            # Meta-info
            'meta': 'command_meta',

            # Data manipulation
            'query': 'command_query',

            # Database structure
            'drop': 'command_drop',
            'recreate': 'command_recreate'
        }

        if len(args) == 0:
            branch_list = list(branch_table.keys())
            branch_list.sort()
            yield from self.send_to_client("You need to specify a DB "
                                           "operation to perform.\r\n"
                                           "Options are:\r\n"
                                           "{}".format(" ".join(branch_list)))
            return

        yield from self.parse_client_input(branch_table, " ".join(args))

    @asyncio.coroutine
    def command_db_config(self, *args):
        """
        Gets/sets provider configuration options.
        """
        if len(args) == 0:
            # Get config
            request = {
                'command': 'db_get_config'
            }
            yield from self.send_to_server(request)
            return

        request = {
            'command': 'db_set_config',
            'option': args[0],
            'value': " ".join(args[1:])
        }
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_meta(self):
        request = {'command': 'meta'}
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_query(self, *args):
        """
        Literal SQL query
        """
        # Make sure the query is in double inverted commas
        raw_string = " ".join(args)
        re_match = re.search(r'^([^"]*)"(([^\]\"|[^"])+)"([^"]*)$', raw_string)
        if re_match is None:
            yield from self.send_to_client(
                "The query to be executed needs to be properly wrapped in "
                "double inverted commas."
            )
            return

        # E.g., query this "is a" test
        pre_args = re_match.group(1)    # 'this '
        query = re_match.group(2)       # 'is a'
        post_args = re_match.group(4)   # ' test'

        logger.debug(
            "Client issued 'query'. "
            "<pre_args: {}, query: {}, post_args: {}>".format(pre_args,
                                                              query,
                                                              post_args)
        )

        request = {
            'command': 'literal_query',
            'query': query,
            'limit': 100  # Don't want to swamp the client with data
            # TODO: Let limit be user-settable?
        }
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_drop(self, *args):
        """
        See what the client wants to drop, then do it.
        """
        if len(args) == 0:
            yield from self.send_to_client("You need to specify a target to "
                                           "drop.")
            return

        request = {
            'command': 'drop',
            'target': args[0]
        }
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_recreate(self, *args):
        """
        See what the client wants to recreate, then do it.
        """
        if len(args) == 0:
            yield from self.send_to_client("You need to specify a target to "
                                           "rebuild.")
            return

        request = {
            'command': 'recreate',
            'target': args[0]
        }
        yield from self.send_to_server(request)

    @asyncio.coroutine
    def command_debugsleep(self, *args):
        if len(args) == 0:
            yield from self.send_to_client("Syntax: debugsleep [seconds]")
            return
        for x in range(0, int(args[0])):
            yield from asyncio.sleep(1)
            yield from self.send_to_client("\r\n** Zzz **")

    # === Format Functions ===
    @asyncio.coroutine
    def format_raw(self, reply):
        return str(reply)

    @asyncio.coroutine
    def format_db_get_config(self, reply):
        output = "DB Provider Configuration\r\n" \
                 "=========================\r\n" \
                 "[Read-Only Options]\r\n\r\n"

        # =======================================================
        # Alignments and headers for configurable options section
        name_width = 4
        val_width = 5
        configurable_list = [
            {
                "name": "Name",
                "value": "Value",
                "desc": "Description"
            },
            {
                "name": "----",
                "value": "-----",
                "desc": "-----------"
            }
        ]
        # =======================================================

        for option in reply:
            if option["read_only"]:
                output += "o {}\r\n    {}\r\n\r\n".format(
                    option["desc"], option["value"]
                )
            else:
                # Might as well figure out the maximum column length here
                name_width = max(name_width, len(option["name"]))
                val_width = max(val_width, len(str(option["value"])))
                configurable_list.append(option)

        output += "[Configurable Options]\r\n\r\n"

        for option in configurable_list:
            output += "{name:<{name_width}}" \
                      "{value:<{val_width}}" \
                      "{desc}\r\n".format(name=option["name"],
                                          value=str(option["value"]),
                                          desc=option["desc"],
                                          name_width=(name_width + 4),
                                          val_width=(val_width + 4))

        output += "\r\nUse 'db config <option_name> <new_value>' to change " \
                  "any of the configurable options."
        return output

    @asyncio.coroutine
    def format_db_set_config(self, reply):
        if reply[1] == "invalid_value":
            return "Invalid value given for '{}'.".format(reply[0])
        elif reply[1] == "invalid_option":
            return "'{}' is not a valid option.".format(reply[0])
        else:
            return "'{}' set to '{}'.".format(reply[0], str(reply[1]))

    @asyncio.coroutine
    def format_literal_query(self, reply):
        warning_msg = "[Warning for Literal SQL Queries]\r\n" \
                      "REMINDER: If the suffixer is not in search mode, " \
                      "suffix search results will be inaccurate.  If the " \
                      "suffixer is in search mode, rebuilding the suffix " \
                      "table will not work. Use the 'db config' command to " \
                      "switch between the two modes."
        return "{}\r\n\r\n{}".format(str(reply), warning_msg)

class TelnetExit(Exception):
    """
    When raised, the main telnet interface will know the client wants to exit
    """

    def __init__(self):
        self.value = "TelnetExit"

    def __str__(self):
        return repr(self.value)
