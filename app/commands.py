import threading
import time

from app.resp import (
    encode_bulk_string,
    encode_error,
    encode_integer,
    encode_simple_string,
)

redis_store = {}
# Absolute expiry time (Unix milliseconds) for keys that have a TTL. Kept in a
# separate dict, as Redis does, so keys without a TTL cost nothing extra.
expirations = {}

# Commands run one at a time, like Redis's single-threaded executor. Each
# client has its own thread, so without this lock a read-modify-write such as
# INCR (or DEL's check-then-delete) could interleave with another client's.
store_lock = threading.Lock()

MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1


def now_ms():
    return time.time_ns() // 1_000_000


def delete_key(key):
    redis_store.pop(key, None)
    expirations.pop(key, None)


def is_expired(key):
    expires_at = expirations.get(key)
    return expires_at is not None and expires_at <= now_ms()


def get_value(key):
    """Return the value for key, deleting it first if it has expired.

    This is lazy (passive) expiry: an expired key is removed the moment a
    command touches it. delete_expired_keys() handles keys nobody reads.
    """
    if is_expired(key):
        delete_key(key)
    return redis_store.get(key)


def delete_expired_keys():
    """Active expiry: remove every key whose TTL has passed."""
    with store_lock:
        now = now_ms()
        for key in [key for key, at in expirations.items() if at <= now]:
            delete_key(key)


def start_expiry_sweeper(interval=0.1):
    """Run active expiry in the background. Set the returned event to stop."""
    stop = threading.Event()

    def sweep():
        while not stop.wait(interval):
            delete_expired_keys()

    threading.Thread(target=sweep, daemon=True).start()
    return stop


def wrong_number_of_arguments(command):
    return encode_error(f"ERR wrong number of arguments for '{command}' command")


def handle_ping(args):
    return encode_simple_string("PONG")


def handle_echo(args):
    if len(args) != 1:
        return wrong_number_of_arguments("echo")
    return encode_bulk_string(args[0])


# SET options that set a TTL, mapped to "how to turn the number into an
# absolute Unix time in milliseconds".
EXPIRY_OPTIONS = {
    "EX": lambda seconds: now_ms() + seconds * 1000,
    "PX": lambda milliseconds: now_ms() + milliseconds,
    "EXAT": lambda unix_seconds: unix_seconds * 1000,
    "PXAT": lambda unix_milliseconds: unix_milliseconds,
}


def handle_set(args):
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

    redis_store[key] = value
    # A plain SET discards any previous TTL, as in Redis.
    if expires_at is None:
        expirations.pop(key, None)
    else:
        expirations[key] = expires_at
    return encode_simple_string("OK")


def handle_get(args):
    if len(args) != 1:
        return wrong_number_of_arguments("get")
    return encode_bulk_string(get_value(args[0]))


def handle_del(args):
    if not args:
        return wrong_number_of_arguments("del")
    deleted_count = 0
    for key in args:
        if get_value(key) is not None:
            delete_key(key)
            deleted_count += 1
    return encode_integer(deleted_count)


def remaining_ttl_ms(key):
    """Milliseconds left, -1 if the key has no TTL, -2 if it does not exist."""
    if get_value(key) is None:
        return -2
    expires_at = expirations.get(key)
    if expires_at is None:
        return -1
    return expires_at - now_ms()


def handle_ttl(args):
    if len(args) != 1:
        return wrong_number_of_arguments("ttl")
    ttl = remaining_ttl_ms(args[0])
    # Round to the nearest second, like Redis.
    return encode_integer(ttl if ttl < 0 else (ttl + 500) // 1000)


def handle_pttl(args):
    if len(args) != 1:
        return wrong_number_of_arguments("pttl")
    return encode_integer(remaining_ttl_ms(args[0]))


def increment(key, amount):
    current = get_value(key)
    if current is None:
        current = b"0"
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
    "TTL": handle_ttl,
    "PTTL": handle_pttl,
}


def execute_command(parts):
    """Run a parsed command (a list of bytes) and return the RESP reply."""
    name = parts[0].decode(errors="replace").upper()
    handler = COMMANDS.get(name)
    if handler is None:
        return encode_error(f"ERR unknown command '{name.lower()}'")
    with store_lock:
        return handler(parts[1:])
