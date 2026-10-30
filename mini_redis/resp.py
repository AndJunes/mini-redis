class ProtocolError(Exception):
    pass


# Buffers input, since a recv() can hold half a command or several of them.
class RespParser:
    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        self._buffer.extend(data)
        commands = []
        while (command := self._parse_command()) is not None:
            commands.append(command)
        return commands

    def _parse_command(self):
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
            end = pos + length
            if len(self._buffer) < end + 2:
                return None
            if self._buffer[end : end + 2] != b"\r\n":
                raise ProtocolError("bulk string is not terminated by CRLF")
            parts.append(bytes(self._buffer[pos:end]))
            pos = end + 2

        del self._buffer[:pos]
        return parts

    def has_pending_data(self):
        return bool(self._buffer)

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


def encode_command(parts):
    return (
        b"*"
        + str(len(parts)).encode()
        + b"\r\n"
        + b"".join(encode_bulk_string(part) for part in parts)
    )
