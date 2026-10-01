from app.resp import encode_bulk_string

redis_store = {}


def handle_ping(args):
    return b"+PONG\r\n"


def handle_echo(args):
    if not args:
        return b"-ERR wrong number of arguments for 'ECHO' command\r\n"
    response = encode_bulk_string(args[0])
    return response


def handle_set(args):
    if len(args) < 2:
        return b"-ERR wrong number of arguments for 'SET' command\r\n"
    key = args[0]
    value = args[1]
    redis_store[key] = value
    return b"+OK\r\n"


def handle_get(args):
    if len(args) < 1:
        return b"-ERR wrong number of arguments for 'GET' command\r\n"
    key = args[0]
    value = redis_store.get(key)
    if value is None:
        return b"$-1\r\n"
    response = encode_bulk_string(value)
    return response


def handle_del(args):
    if len(args) < 1:
        return b"-ERR wrong number of arguments for 'DEL' command\r\n"
    deleted_count = 0
    for key in args:
        if key in redis_store:
            del redis_store[key]
            deleted_count += 1
    response = f":{deleted_count}\r\n".encode()
    return response


COMMANDS = {
    "PING": handle_ping,
    "ECHO": handle_echo,
    "SET": handle_set,
    "GET": handle_get,
    "DEL": handle_del,
}
