import threading

import pytest

from app.commands import execute_command


def run(*parts):
    return execute_command([part.encode() for part in parts])


def test_ping():
    assert run("PING") == b"+PONG\r\n"


def test_command_names_are_case_insensitive():
    assert run("ping") == b"+PONG\r\n"


def test_echo():
    assert run("ECHO", "hello") == b"$5\r\nhello\r\n"


def test_set_and_get():
    assert run("SET", "name", "Andrea") == b"+OK\r\n"
    assert run("GET", "name") == b"$6\r\nAndrea\r\n"


def test_set_overwrites():
    run("SET", "name", "Andrea")
    run("SET", "name", "Ana")
    assert run("GET", "name") == b"$3\r\nAna\r\n"


def test_get_missing_key_returns_null():
    assert run("GET", "missing") == b"$-1\r\n"


def test_del_returns_number_of_deleted_keys():
    run("SET", "a", "1")
    run("SET", "b", "2")
    assert run("DEL", "a", "b", "c") == b":2\r\n"
    assert run("GET", "a") == b"$-1\r\n"
    assert run("DEL", "a") == b":0\r\n"


def test_unknown_command():
    assert run("FOO") == b"-ERR unknown command 'foo'\r\n"


@pytest.mark.parametrize(
    ("parts", "name"),
    [
        (["ECHO"], "echo"),
        (["ECHO", "a", "b"], "echo"),
        (["SET", "key"], "set"),
        (["GET"], "get"),
        (["DEL"], "del"),
        (["INCR"], "incr"),
        (["DECR", "a", "b"], "decr"),
    ],
)
def test_wrong_number_of_arguments(parts, name):
    expected = f"-ERR wrong number of arguments for '{name}' command\r\n"
    assert run(*parts) == expected.encode()


def test_incr_creates_missing_keys_at_zero():
    assert run("INCR", "counter") == b":1\r\n"
    assert run("INCR", "counter") == b":2\r\n"
    assert run("GET", "counter") == b"$1\r\n2\r\n"


def test_decr():
    run("SET", "counter", "10")
    assert run("DECR", "counter") == b":9\r\n"
    assert run("DECR", "missing") == b":-1\r\n"


@pytest.mark.parametrize("value", ["abc", " 7", "+7", "07", "1.5", ""])
def test_incr_rejects_non_integers(value):
    run("SET", "key", value)
    assert run("INCR", "key") == b"-ERR value is not an integer or out of range\r\n"


def test_incr_overflow():
    run("SET", "key", str(2**63 - 1))
    assert run("INCR", "key") == b"-ERR increment or decrement would overflow\r\n"
    run("SET", "key", str(-(2**63)))
    assert run("DECR", "key") == b"-ERR increment or decrement would overflow\r\n"


def test_concurrent_incr_does_not_lose_updates():
    threads_count, increments = 8, 500

    def worker():
        for _ in range(increments):
            run("INCR", "counter")

    threads = [threading.Thread(target=worker) for _ in range(threads_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    expected = str(threads_count * increments)
    assert run("GET", "counter") == f"${len(expected)}\r\n{expected}\r\n".encode()
