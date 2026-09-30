# mini-redis

A Redis-compatible server written from scratch in Python, with no third-party dependencies.

It speaks the [RESP protocol](https://redis.io/docs/latest/develop/reference/protocol-spec/),
so it works with standard clients like `redis-cli`.

## Getting started

Requirements: Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```sh
./your_program.sh
```

The server listens on `localhost:6379`. From another terminal:

```sh
redis-cli PING
# PONG

redis-cli ECHO "hello world"
# "hello world"
```

## Features

- TCP server on port 6379
- Concurrent clients (one thread per connection)
- RESP parser
- Commands: `PING`, `ECHO`
- RESP error replies for unknown commands and wrong number of arguments

## Project structure

```
app/
├── main.py   # TCP server, connection handling and command dispatch
└── resp.py   # RESP protocol parser
```

## Roadmap

- [ ] `SET` / `GET`
- [ ] Key expiry (`PX`)
- [ ] Binary-safe parsing using bulk string lengths
- [ ] Handle partial and pipelined messages
- [ ] Test suite
