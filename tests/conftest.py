import socket
import threading

import pytest

from app import commands
from app.main import serve


@pytest.fixture(autouse=True)
def empty_store():
    commands.redis_store.clear()
    commands.expirations.clear()
    yield
    commands.disable_aof()
    commands.redis_store.clear()
    commands.expirations.clear()


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
def server_address():
    server_socket = socket.create_server(("localhost", 0))
    threading.Thread(target=serve, args=(server_socket,), daemon=True).start()
    yield server_socket.getsockname()[:2]
    server_socket.close()
