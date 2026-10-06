"""End-to-end tests that talk to a real server over TCP."""

import socket

import pytest


@pytest.fixture
def client(server_address):
    with socket.create_connection(server_address, timeout=2) as connection:
        yield connection


def receive(connection, expected):
    data = b""
    while len(data) < len(expected):
        chunk = connection.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_ping(client):
    client.sendall(b"*1\r\n$4\r\nPING\r\n")
    assert receive(client, b"+PONG\r\n") == b"+PONG\r\n"


def test_command_split_across_packets(client):
    client.sendall(b"*2\r\n$4\r\nEC")
    client.sendall(b"HO\r\n$2\r\nhi\r\n")
    assert receive(client, b"$2\r\nhi\r\n") == b"$2\r\nhi\r\n"


def test_pipelined_commands_are_answered_in_order(client):
    client.sendall(
        b"*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$1\r\nv\r\n"
        b"*2\r\n$3\r\nGET\r\n$1\r\nk\r\n"
        b"*1\r\n$4\r\nPING\r\n"
    )
    expected = b"+OK\r\n$1\r\nv\r\n+PONG\r\n"
    assert receive(client, expected) == expected


def test_clients_share_the_same_store(server_address):
    with socket.create_connection(server_address, timeout=2) as writer:
        writer.sendall(b"*3\r\n$3\r\nSET\r\n$4\r\nname\r\n$6\r\nAndrea\r\n")
        assert receive(writer, b"+OK\r\n") == b"+OK\r\n"
    with socket.create_connection(server_address, timeout=2) as reader:
        reader.sendall(b"*2\r\n$3\r\nGET\r\n$4\r\nname\r\n")
        assert receive(reader, b"$6\r\nAndrea\r\n") == b"$6\r\nAndrea\r\n"


def test_concurrent_clients(server_address):
    first = socket.create_connection(server_address, timeout=2)
    second = socket.create_connection(server_address, timeout=2)
    with first, second:
        second.sendall(b"*1\r\n$4\r\nPING\r\n")
        assert receive(second, b"+PONG\r\n") == b"+PONG\r\n"
        first.sendall(b"*1\r\n$4\r\nPING\r\n")
        assert receive(first, b"+PONG\r\n") == b"+PONG\r\n"


def test_protocol_error_closes_the_connection(client):
    client.sendall(b"hello\r\n")
    reply = client.recv(4096)
    assert reply.startswith(b"-ERR Protocol error")
    assert client.recv(4096) == b""
