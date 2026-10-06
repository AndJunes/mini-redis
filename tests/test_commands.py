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
    ],
)
def test_wrong_number_of_arguments(parts, name):
    expected = f"-ERR wrong number of arguments for '{name}' command\r\n"
    assert run(*parts) == expected.encode()
