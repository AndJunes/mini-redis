import time

import pytest

from app import commands
from app.commands import execute_command


def run(*parts):
    return execute_command([str(part).encode() for part in parts])


def test_key_with_px_expires(clock):
    assert run("SET", "session", "abc", "PX", 100) == b"+OK\r\n"
    clock.advance(99)
    assert run("GET", "session") == b"$3\r\nabc\r\n"
    clock.advance(1)
    assert run("GET", "session") == b"$-1\r\n"


def test_key_with_ex_expires(clock):
    run("SET", "session", "abc", "EX", 2)
    clock.advance(1999)
    assert run("GET", "session") == b"$3\r\nabc\r\n"
    clock.advance(1)
    assert run("GET", "session") == b"$-1\r\n"


def test_absolute_expiry_options(clock):
    run("SET", "a", "1", "PXAT", clock.now + 50)
    run("SET", "b", "1", "EXAT", clock.now // 1000 + 1)
    clock.advance(1000)
    assert run("GET", "a") == b"$-1\r\n"
    assert run("GET", "b") == b"$-1\r\n"


def test_options_are_case_insensitive(clock):
    run("SET", "session", "abc", "px", 10)
    clock.advance(10)
    assert run("GET", "session") == b"$-1\r\n"


def test_plain_set_removes_ttl(clock):
    run("SET", "key", "old", "PX", 100)
    run("SET", "key", "new")
    clock.advance(1000)
    assert run("GET", "key") == b"$3\r\nnew\r\n"


def test_expired_key_is_removed_from_memory(clock):
    run("SET", "key", "value", "PX", 10)
    clock.advance(10)
    run("GET", "key")
    assert b"key" not in commands.redis_store
    assert b"key" not in commands.expirations


def test_del_does_not_count_expired_keys(clock):
    run("SET", "key", "value", "PX", 10)
    clock.advance(10)
    assert run("DEL", "key") == b":0\r\n"


def test_incr_on_expired_key_starts_from_zero(clock):
    run("SET", "counter", "41", "PX", 10)
    clock.advance(10)
    assert run("INCR", "counter") == b":1\r\n"


def test_incr_keeps_the_ttl(clock):
    run("SET", "counter", "1", "PX", 100)
    run("INCR", "counter")
    clock.advance(100)
    assert run("GET", "counter") == b"$-1\r\n"


def test_ttl_and_pttl(clock):
    assert run("TTL", "missing") == b":-2\r\n"
    assert run("PTTL", "missing") == b":-2\r\n"
    run("SET", "forever", "x")
    assert run("TTL", "forever") == b":-1\r\n"
    run("SET", "session", "abc", "PX", 10_000)
    assert run("PTTL", "session") == b":10000\r\n"
    clock.advance(2_400)
    assert run("PTTL", "session") == b":7600\r\n"
    assert run("TTL", "session") == b":8\r\n"
    clock.advance(7_600)
    assert run("TTL", "session") == b":-2\r\n"


def test_active_expiry_removes_keys_nobody_reads(clock):
    run("SET", "a", "1", "PX", 10)
    run("SET", "b", "2", "PX", 1000)
    run("SET", "c", "3")
    clock.advance(10)
    commands.delete_expired_keys()
    assert set(commands.redis_store) == {b"b", b"c"}
    assert set(commands.expirations) == {b"b"}


def test_background_sweeper_runs_with_the_real_clock():
    stop = commands.start_expiry_sweeper(interval=0.01)
    try:
        run("SET", "key", "value", "PX", 20)
        deadline = time.monotonic() + 2
        while b"key" in commands.redis_store and time.monotonic() < deadline:
            time.sleep(0.01)
        assert b"key" not in commands.redis_store
    finally:
        stop.set()


@pytest.mark.parametrize(
    ("options", "error"),
    [
        (["PX"], b"-ERR syntax error\r\n"),
        (["FOO", "10"], b"-ERR syntax error\r\n"),
        (["PX", "10", "EX", "1"], b"-ERR syntax error\r\n"),
        (["PX", "abc"], b"-ERR value is not an integer or out of range\r\n"),
        (["PX", "0"], b"-ERR invalid expire time in 'set' command\r\n"),
        (["EX", "-5"], b"-ERR invalid expire time in 'set' command\r\n"),
    ],
)
def test_invalid_set_options(options, error):
    assert run("SET", "key", "value", *options) == error
    assert run("GET", "key") == b"$-1\r\n"


@pytest.mark.parametrize("command", ["TTL", "PTTL"])
def test_ttl_wrong_number_of_arguments(command):
    expected = f"-ERR wrong number of arguments for '{command.lower()}' command\r\n"
    assert run(command) == expected.encode()
