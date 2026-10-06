import socket
import threading

import pytest

from app import commands
from app.main import serve


@pytest.fixture(autouse=True)
def empty_store():
    commands.redis_store.clear()
    yield
    commands.redis_store.clear()


@pytest.fixture
def server_address():
    """Start a real server on a free port and return its (host, port)."""
    server_socket = socket.create_server(("localhost", 0))
    threading.Thread(target=serve, args=(server_socket,), daemon=True).start()
    yield server_socket.getsockname()[:2]
    server_socket.close()
