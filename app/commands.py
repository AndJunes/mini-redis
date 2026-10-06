from app.resp import (
    encode_bulk_string,
    encode_error,
    encode_integer,
    encode_simple_string,
)

redis_store = {}


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


COMMANDS = {
    "PING": handle_ping,
    "ECHO": handle_echo,
    "SET": handle_set,
    "GET": handle_get,
    "DEL": handle_del,
}


def execute_command(parts):
    """Run a parsed command (a list of bytes) and return the RESP reply."""
    name = parts[0].decode(errors="replace").upper()
    handler = COMMANDS.get(name)
    if handler is None:
        return encode_error(f"ERR unknown command '{name.lower()}'")
    return handler(parts[1:])
