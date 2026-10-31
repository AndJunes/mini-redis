"""Command handlers and the in-memory key-value store."""

import threading
import time
from collections.abc import Callable
from typing import ClassVar

from mini_redis import persistence
from mini_redis.resp import (
    encode_bulk_string,
    encode_error,
    encode_integer,
    encode_simple_string,
)

MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def wrong_number_of_arguments(command: str) -> bytes:
    return encode_error(f"ERR wrong number of arguments for '{command}' command")


EXPIRY_OPTIONS: dict[str, Callable[[int], int]] = {
    "EX": lambda seconds: now_ms() + seconds * 1000,
    "PX": lambda milliseconds: now_ms() + milliseconds,
    "EXAT": lambda unix_seconds: unix_seconds * 1000,
    "PXAT": lambda unix_milliseconds: unix_milliseconds,
}

WRITE_COMMANDS = {"SET", "DEL", "INCR", "DECR"}


class Database:
    """The key-value store, its expirations and the optional AOF."""

    def __init__(self) -> None:
        self.store: dict[bytes, bytes] = {}
        self.expirations: dict[bytes, int] = {}  # key -> expiry time in Unix ms
        # One command at a time, like Redis, so INCR and DEL can't interleave.
        self.lock = threading.Lock()
        self.aof: persistence.AppendOnlyFile | None = None

    def delete_key(self, key: bytes) -> None:
        self.store.pop(key, None)
        self.expirations.pop(key, None)

    def is_expired(self, key: bytes) -> bool:
        expires_at = self.expirations.get(key)
        return expires_at is not None and expires_at <= now_ms()

    def get_value(self, key: bytes) -> bytes | None:
        if self.is_expired(key):
            self.delete_key(key)
        return self.store.get(key)

    def delete_expired_keys(self) -> None:
        with self.lock:
            now = now_ms()
            for key in [key for key, at in self.expirations.items() if at <= now]:
                self.delete_key(key)

    def start_expiry_sweeper(self, interval: float = 0.1) -> threading.Event:
        """Delete expired keys in the background until the returned event is set."""
        stop = threading.Event()

        def sweep() -> None:
            while not stop.wait(interval):
                self.delete_expired_keys()

        threading.Thread(target=sweep, daemon=True).start()
        return stop

    def handle_ping(self, args: list[bytes]) -> bytes:
        return encode_simple_string("PONG")

    def handle_echo(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("echo")
        return encode_bulk_string(args[0])

    def handle_set(self, args: list[bytes]) -> bytes:
        if len(args) < 2:
            return wrong_number_of_arguments("set")
        key, value, options = args[0], args[1], args[2:]

        expires_at = None
        if options:
            if len(options) != 2:
                return encode_error("ERR syntax error")
            option = options[0].decode(errors="replace").upper()
            if option not in EXPIRY_OPTIONS:
                return encode_error("ERR syntax error")
            try:
                amount = int(options[1])
            except ValueError:
                return encode_error("ERR value is not an integer or out of range")
            if amount <= 0:
                return encode_error("ERR invalid expire time in 'set' command")
            expires_at = EXPIRY_OPTIONS[option](amount)

        self.store[key] = value
        if expires_at is None:
            self.expirations.pop(key, None)
        else:
            self.expirations[key] = expires_at
        return encode_simple_string("OK")

    def handle_get(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("get")
        return encode_bulk_string(self.get_value(args[0]))

    def handle_del(self, args: list[bytes]) -> bytes:
        if not args:
            return wrong_number_of_arguments("del")
        deleted_count = 0
        for key in args:
            if self.get_value(key) is not None:
                self.delete_key(key)
                deleted_count += 1
        return encode_integer(deleted_count)

    def remaining_ttl_ms(self, key: bytes) -> int:
        if self.get_value(key) is None:
            return -2
        expires_at = self.expirations.get(key)
        if expires_at is None:
            return -1
        return expires_at - now_ms()

    def handle_ttl(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("ttl")
        ttl = self.remaining_ttl_ms(args[0])
        return encode_integer(ttl if ttl < 0 else (ttl + 500) // 1000)

    def handle_pttl(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("pttl")
        return encode_integer(self.remaining_ttl_ms(args[0]))

    def increment(self, key: bytes, amount: int) -> bytes:
        current = self.get_value(key)
        if current is None:
            current = b"0"
        number: int | None
        try:
            number = int(current)
        except ValueError:
            number = None
        # int() accepts " 7" and "+7", Redis doesn't
        if number is None or str(number).encode() != current:
            return encode_error("ERR value is not an integer or out of range")
        result = number + amount
        if not MIN_INT64 <= result <= MAX_INT64:
            return encode_error("ERR increment or decrement would overflow")
        self.store[key] = str(result).encode()
        return encode_integer(result)

    def handle_incr(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("incr")
        return self.increment(args[0], 1)

    def handle_decr(self, args: list[bytes]) -> bytes:
        if len(args) != 1:
            return wrong_number_of_arguments("decr")
        return self.increment(args[0], -1)

    COMMANDS: ClassVar[dict[str, Callable[[Database, list[bytes]], bytes]]] = {
        "PING": handle_ping,
        "ECHO": handle_echo,
        "SET": handle_set,
        "GET": handle_get,
        "DEL": handle_del,
        "INCR": handle_incr,
        "DECR": handle_decr,
        "TTL": handle_ttl,
        "PTTL": handle_pttl,
    }

    # Log the resulting state with an absolute TTL instead of the original
    # command, so replaying "SET k v EX 60" later doesn't give the key a new minute.
    def state_record(self, key: bytes) -> list[bytes]:
        value = self.get_value(key)
        if value is None:
            return [b"DEL", key]
        record = [b"SET", key, value]
        if key in self.expirations:
            record += [b"PXAT", str(self.expirations[key]).encode()]
        return record

    def log_write(self, name: str, args: list[bytes], reply: bytes) -> None:
        if self.aof is None or name not in WRITE_COMMANDS or reply.startswith(b"-"):
            return
        if name == "DEL":
            if reply != b":0\r\n":
                self.aof.append([b"DEL", *args])
        else:
            self.aof.append(self.state_record(args[0]))

    def execute_command(self, parts: list[bytes]) -> bytes:
        """Run one parsed command and return its RESP-encoded reply."""
        name = parts[0].decode(errors="replace").upper()
        handler = self.COMMANDS.get(name)
        if handler is None:
            return encode_error(f"ERR unknown command '{name.lower()}'")
        with self.lock:
            reply = handler(self, parts[1:])
            self.log_write(name, parts[1:], reply)
            return reply

    def enable_aof(self, path: str, fsync: str = "everysec") -> tuple[int, bool]:
        """Replay the file, compact it, and log every write from now on."""
        commands, truncated = persistence.read_commands(path)
        for parts in commands:
            self.execute_command(parts)
        with self.lock:
            snapshot = [self.state_record(key) for key in list(self.store)]
            snapshot = [record for record in snapshot if record[0] == b"SET"]
            persistence.write_snapshot(path, snapshot)
            self.aof = persistence.AppendOnlyFile(path, fsync)
        return len(snapshot), truncated

    def disable_aof(self) -> None:
        if self.aof is not None:
            self.aof.close()
            self.aof = None
