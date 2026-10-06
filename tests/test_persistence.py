import socket
import subprocess
import sys
import time

import pytest

from app import commands
from app.commands import disable_aof, enable_aof, execute_command
from app.persistence import read_commands
from app.resp import ProtocolError


def run(*parts):
    return execute_command([str(part).encode() for part in parts])


def restart(path):
    disable_aof()
    commands.redis_store.clear()
    commands.expirations.clear()
    return enable_aof(path)


@pytest.fixture
def aof_path(tmp_path):
    return str(tmp_path / "appendonly.aof")


def test_writes_survive_a_restart(aof_path):
    enable_aof(aof_path)
    run("SET", "name", "Andrea")
    run("SET", "city", "Córdoba")
    run("DEL", "city")
    run("INCR", "visits")
    run("INCR", "visits")

    assert restart(aof_path) == (2, False)
    assert run("GET", "name") == b"$6\r\nAndrea\r\n"
    assert run("GET", "city") == b"$-1\r\n"
    assert run("GET", "visits") == b"$1\r\n2\r\n"


def test_binary_values_survive_a_restart(aof_path):
    enable_aof(aof_path)
    execute_command([b"SET", b"blob", b"\x00\xff\r\n\x01"])
    restart(aof_path)
    assert execute_command([b"GET", b"blob"]) == b"$5\r\n\x00\xff\r\n\x01\r\n"


def test_relative_ttl_is_logged_as_absolute_time(aof_path, clock):
    enable_aof(aof_path)
    run("SET", "session", "abc", "EX", 60)
    logged, _ = read_commands(aof_path)
    expected_at = str(clock.now + 60_000).encode()
    assert logged == [[b"SET", b"session", b"abc", b"PXAT", expected_at]]


def test_ttl_keeps_counting_while_the_server_is_down(aof_path, clock):
    enable_aof(aof_path)
    run("SET", "session", "abc", "EX", 60)
    clock.advance(30_000)
    restart(aof_path)
    assert run("TTL", "session") == b":30\r\n"
    clock.advance(30_000)
    assert run("GET", "session") == b"$-1\r\n"


def test_keys_that_expired_while_down_are_not_restored(aof_path, clock):
    enable_aof(aof_path)
    run("SET", "session", "abc", "PX", 100)
    run("SET", "name", "Andrea")
    clock.advance(100)
    assert restart(aof_path) == (1, False)
    assert run("GET", "session") == b"$-1\r\n"


def test_incr_on_a_key_with_ttl_is_replayed_correctly(aof_path, clock):
    enable_aof(aof_path)
    run("SET", "counter", "41", "PX", 100)
    clock.advance(100)
    run("INCR", "counter")  # the old key had expired, so this starts from 0
    clock.advance(1_000)
    restart(aof_path)
    assert run("GET", "counter") == b"$1\r\n1\r\n"
    assert run("TTL", "counter") == b":-1\r\n"


def test_failed_and_read_only_commands_are_not_logged(aof_path):
    enable_aof(aof_path)
    run("GET", "missing")
    run("PING")
    run("SET", "key")
    run("SET", "text", "abc")
    run("INCR", "text")
    run("DEL", "missing")
    logged, _ = read_commands(aof_path)
    assert logged == [[b"SET", b"text", b"abc"]]


def test_file_is_compacted_on_startup(aof_path):
    enable_aof(aof_path)
    for number in range(100):
        run("SET", "counter", number)
    run("SET", "temp", "x")
    run("DEL", "temp")
    restart(aof_path)
    logged, _ = read_commands(aof_path)
    assert logged == [[b"SET", b"counter", b"99"]]


def test_truncated_tail_is_ignored(aof_path):
    enable_aof(aof_path)
    run("SET", "name", "Andrea")
    disable_aof()
    with open(aof_path, "ab") as file:
        file.write(b"*3\r\n$3\r\nSET\r\n$3\r\nage")  # crash mid-write
    assert restart(aof_path) == (1, True)
    assert run("GET", "name") == b"$6\r\nAndrea\r\n"
    run("SET", "age", "26")
    assert restart(aof_path) == (2, False)


def test_corrupt_file_refuses_to_load(aof_path):
    with open(aof_path, "wb") as file:
        file.write(b"this is not RESP\r\n")
    with pytest.raises(ProtocolError):
        enable_aof(aof_path)


def free_port():
    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        return probe.getsockname()[1]


def send(port, command):
    with socket.create_connection(("localhost", port), timeout=2) as connection:
        connection.sendall(command)
        return connection.recv(4096)


def start_server(port, aof_path):
    process = subprocess.Popen(
        [sys.executable, "-m", "app.main", "--port", str(port), "--aof", aof_path],
        stdout=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            send(port, b"*1\r\n$4\r\nPING\r\n")
            return process
        except OSError:
            time.sleep(0.05)
    process.kill()
    raise RuntimeError("server did not start")


def test_real_server_restores_data_after_being_killed(aof_path):
    port = free_port()
    server = start_server(port, aof_path)
    try:
        assert send(port, b"*3\r\n$3\r\nSET\r\n$4\r\nname\r\n$6\r\nAndrea\r\n") == (
            b"+OK\r\n"
        )
    finally:
        server.kill()  # no clean shutdown, like a crash
        server.wait()

    server = start_server(port, aof_path)
    try:
        assert send(port, b"*2\r\n$3\r\nGET\r\n$4\r\nname\r\n") == b"$6\r\nAndrea\r\n"
    finally:
        server.kill()
        server.wait()
