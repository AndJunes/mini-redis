import socket
import threading

import pytest

from mini_redis import commands
from mini_redis.commands import Database
from mini_redis.main import serve


@pytest.fixture
def database():
    database = Database()
    yield database
    database.disable_aof()


@pytest.fixture
def run(database):
    def run(*parts):
        return database.execute_command([str(part).encode() for part in parts])

    return run


class FakeClock:
    def __init__(self):
        self.now = 1_700_000_000_000

    def advance(self, milliseconds):
        self.now += milliseconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(commands, "now_ms", lambda: fake.now)
    return fake


@pytest.fixture
def server_address(database):
    server_socket = socket.create_server(("localhost", 0))
    threading.Thread(target=serve, args=(server_socket, database), daemon=True).start()
    yield server_socket.getsockname()[:2]
    server_socket.close()
