import pytest

from app.resp import (
    ProtocolError,
    RespParser,
    encode_bulk_string,
    encode_error,
    encode_integer,
    encode_simple_string,
)


def test_parses_a_single_command():
    assert RespParser().feed(b"*1\r\n$4\r\nPING\r\n") == [[b"PING"]]


def test_parses_arguments():
    data = b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n"
    assert RespParser().feed(data) == [[b"SET", b"key", b"value"]]


def test_values_may_contain_crlf():
    data = b"*2\r\n$4\r\nECHO\r\n$12\r\nhello\r\nworld\r\n"
    assert RespParser().feed(data) == [[b"ECHO", b"hello\r\nworld"]]


def test_values_may_be_empty():
    assert RespParser().feed(b"*2\r\n$4\r\nECHO\r\n$0\r\n\r\n") == [[b"ECHO", b""]]


def test_buffers_partial_commands_until_complete():
    parser = RespParser()
    assert parser.feed(b"*2\r\n$4\r\nEC") == []
    assert parser.feed(b"HO\r\n$5\r\nhel") == []
    assert parser.feed(b"lo\r\n") == [[b"ECHO", b"hello"]]


def test_byte_by_byte_input():
    parser = RespParser()
    data = b"*1\r\n$4\r\nPING\r\n"
    results = [parser.feed(data[i : i + 1]) for i in range(len(data))]
    assert results[-1] == [[b"PING"]]
    assert all(result == [] for result in results[:-1])


def test_parses_pipelined_commands():
    data = b"*1\r\n$4\r\nPING\r\n*2\r\n$3\r\nGET\r\n$1\r\nk\r\n"
    assert RespParser().feed(data) == [[b"PING"], [b"GET", b"k"]]


def test_keeps_the_rest_of_a_pipeline_for_later():
    parser = RespParser()
    assert parser.feed(b"*1\r\n$4\r\nPING\r\n*1\r\n$4\r\nPI") == [[b"PING"]]
    assert parser.feed(b"NG\r\n") == [[b"PING"]]


@pytest.mark.parametrize(
    "data",
    [
        b"PING\r\n",
        b"*1\r\n+PING\r\n",
        b"*x\r\n",
        b"*0\r\n",
        b"*1\r\n$-1\r\n",
        b"*1\r\n$4\r\nPINGXX",
    ],
)
def test_rejects_invalid_input(data):
    with pytest.raises(ProtocolError):
        RespParser().feed(data)


def test_encoders():
    assert encode_simple_string("OK") == b"+OK\r\n"
    assert encode_error("ERR boom") == b"-ERR boom\r\n"
    assert encode_integer(42) == b":42\r\n"
    assert encode_bulk_string(b"hello") == b"$5\r\nhello\r\n"
    assert encode_bulk_string(None) == b"$-1\r\n"


def test_bulk_string_length_is_in_bytes():
    assert encode_bulk_string("año".encode()) == b"$4\r\na\xc3\xb1o\r\n"
