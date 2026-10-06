class ProtocolError(Exception):
    """Raised when a client sends bytes that are not valid RESP."""


class RespParser:
    """Incremental parser for client commands (RESP arrays of bulk strings).

    TCP delivers a byte stream, not messages: a single recv() may contain half
    a command or several pipelined ones. feed() buffers incoming bytes and
    returns every command that is complete so far, keeping the rest for the
    next call.
    """

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        self._buffer.extend(data)
        commands = []
        while (command := self._parse_command()) is not None:
            commands.append(command)
        return commands

    def _parse_command(self):
        # Parse with a local cursor and only consume the buffer once a full
        # command is available, so partial input stays for the next feed().
        header = self._read_line(0)
        if header is None:
            return None
        line, pos = header
        if line[:1] != b"*":
            raise ProtocolError(f"expected '*', got {line[:1]!r}")
        count = self._parse_length(line[1:])
        if count == 0:
            raise ProtocolError("empty command")

        parts = []
        for _ in range(count):
            header = self._read_line(pos)
            if header is None:
                return None
            line, pos = header
            if line[:1] != b"$":
                raise ProtocolError(f"expected '$', got {line[:1]!r}")
            length = self._parse_length(line[1:])
            # The length tells us exactly how many bytes to take, so values
            # may contain any byte, including "\r\n" (binary-safe).
            end = pos + length
            if len(self._buffer) < end + 2:
                return None
            if self._buffer[end : end + 2] != b"\r\n":
                raise ProtocolError("bulk string is not terminated by CRLF")
            parts.append(bytes(self._buffer[pos:end]))
            pos = end + 2

        del self._buffer[:pos]
        return parts

    def _read_line(self, pos):
        end = self._buffer.find(b"\r\n", pos)
        if end == -1:
            return None
        return bytes(self._buffer[pos:end]), end + 2

    @staticmethod
    def _parse_length(raw):
        try:
            value = int(raw)
        except ValueError:
            raise ProtocolError(f"invalid length {raw!r}") from None
        if value < 0:
            raise ProtocolError(f"invalid length {raw!r}")
        return value


def encode_simple_string(value):
    return b"+" + value.encode() + b"\r\n"


def encode_error(message):
    return b"-" + message.encode() + b"\r\n"


def encode_integer(value):
    return b":" + str(value).encode() + b"\r\n"


def encode_bulk_string(value):
    if value is None:
        return b"$-1\r\n"
    return b"$" + str(len(value)).encode() + b"\r\n" + value + b"\r\n"
