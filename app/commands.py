import threading

from app.resp import (
    encode_bulk_string,
    encode_error,
    encode_integer,
    encode_simple_string,
)

redis_store = {}

# Commands run one at a time, like Redis's single-threaded executor. Each
# client has its own thread, so without this lock a read-modify-write such as
# INCR (or DEL's check-then-delete) could interleave with another client's.
store_lock = threading.Lock()

MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1


def wrong_number_of_arguments(command):
    return encode_error(f"ERR wrong number of arguments for '{command}' command")


def handle_ping(args):
    return encode_simple_string("PONG")


def handle_echo(args):
    if len(args) != 1:
        return wrong_number_of_arguments("echo")
    return encode_bulk_string(args[0])


def handle_set(args):
    if len(args) < 2:
        return wrong_number_of_arguments("set")
    key, value = args[0], args[1]
    redis_store[key] = value
    return encode_simple_string("OK")


def handle_get(args):
    if len(args) != 1:
        return wrong_number_of_arguments("get")
    return encode_bulk_string(redis_store.get(args[0]))


def handle_del(args):
    if not args:
        return wrong_number_of_arguments("del")
    deleted_count = 0
    for key in args:
        if key in redis_store:
            del redis_store[key]
            deleted_count += 1
    return encode_integer(deleted_count)


def increment(key, amount):
    current = redis_store.get(key, b"0")
    try:
        number = int(current)
    except ValueError:
        number = None
    # int() accepts things like b" 7" or b"+7"; Redis only accepts the
    # canonical form, so the value must round-trip exactly.
    if number is None or str(number).encode() != current:
        return encode_error("ERR value is not an integer or out of range")
    result = number + amount
    if not MIN_INT64 <= result <= MAX_INT64:
        return encode_error("ERR increment or decrement would overflow")
    redis_store[key] = str(result).encode()
    return encode_integer(result)


def handle_incr(args):
    if len(args) != 1:
        return wrong_number_of_arguments("incr")
    return increment(args[0], 1)


def handle_decr(args):
    if len(args) != 1:
        return wrong_number_of_arguments("decr")
    return increment(args[0], -1)


COMMANDS = {
    "PING": handle_ping,
    "ECHO": handle_echo,
    "SET": handle_set,
    "GET": handle_get,
    "DEL": handle_del,
    "INCR": handle_incr,
    "DECR": handle_decr,
}


def execute_command(parts):
    """Run a parsed command (a list of bytes) and return the RESP reply."""
    name = parts[0].decode(errors="replace").upper()
    handler = COMMANDS.get(name)
    if handler is None:
        return encode_error(f"ERR unknown command '{name.lower()}'")
    with store_lock:
        return handler(parts[1:])
