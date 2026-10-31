"""Parser and encoders for RESP, the Redis serialization protocol."""


class ProtocolError(Exception):
    pass


# Caps match Redis, so a bad or hostile length can't balloon the buffer:
# 1M elements per command and 512 MB per value (proto-max-bulk-len).
MAX_ARRAY_LENGTH = 1024 * 1024
MAX_BULK_LENGTH = 512 * 1024 * 1024

# A header line ("*3", "$1024") never comes close to this.
MAX_LINE_LENGTH = 64 * 1024


class RespParser:
    """Buffers input, since a recv() can hold half a command or several of them."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[list[bytes]]:
        """Add received bytes and return every command they complete."""
        self._buffer.extend(data)
        commands = []
        while (command := self._parse_command()) is not None:
            commands.append(command)
        return commands

    def _parse_command(self) -> list[bytes] | None:
        header = self._read_line(0)
        if header is None:
            return None
        line, pos = header
        if line[:1] != b"*":
            raise ProtocolError(f"expected '*', got {line[:1]!r}")
        count = self._parse_length(line[1:])
        if count == 0:
            raise ProtocolError("empty command")
        if count > MAX_ARRAY_LENGTH:
            raise ProtocolError("invalid multibulk length")

        parts = []
        for _ in range(count):
            header = self._read_line(pos)
            if header is None:
                return None
            line, pos = header
            if line[:1] != b"$":
                raise ProtocolError(f"expected '$', got {line[:1]!r}")
            length = self._parse_length(line[1:])
            if length > MAX_BULK_LENGTH:
                raise ProtocolError("invalid bulk length")
            end = pos + length
            if len(self._buffer) < end + 2:
                return None
            if self._buffer[end : end + 2] != b"\r\n":
                raise ProtocolError("bulk string is not terminated by CRLF")
            parts.append(bytes(self._buffer[pos:end]))
            pos = end + 2

        del self._buffer[:pos]
        return parts

    def has_pending_data(self) -> bool:
        return bool(self._buffer)

    def _read_line(self, pos: int) -> tuple[bytes, int] | None:
        end = self._buffer.find(b"\r\n", pos)
        if end == -1:
            if len(self._buffer) - pos > MAX_LINE_LENGTH:
                raise ProtocolError("too big inline request")
            return None
        return bytes(self._buffer[pos:end]), end + 2

    @staticmethod
    def _parse_length(raw: bytes) -> int:
        try:
            value = int(raw)
        except ValueError:
            raise ProtocolError(f"invalid length {raw!r}") from None
        if value < 0:
            raise ProtocolError(f"invalid length {raw!r}")
        return value


def encode_simple_string(value: str) -> bytes:
    return b"+" + value.encode() + b"\r\n"


def encode_error(message: str) -> bytes:
    return b"-" + message.encode() + b"\r\n"


def encode_integer(value: int) -> bytes:
    return b":" + str(value).encode() + b"\r\n"


def encode_bulk_string(value: bytes | None) -> bytes:
    if value is None:
        return b"$-1\r\n"
    return b"$" + str(len(value)).encode() + b"\r\n" + value + b"\r\n"


def encode_command(parts: list[bytes]) -> bytes:
    return (
        b"*"
        + str(len(parts)).encode()
        + b"\r\n"
        + b"".join(encode_bulk_string(part) for part in parts)
    )
