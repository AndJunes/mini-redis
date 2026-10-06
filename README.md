# mini-redis

[![CI](https://github.com/AndJunes/mini-redis/actions/workflows/ci.yml/badge.svg)](https://github.com/AndJunes/mini-redis/actions/workflows/ci.yml)

A Redis-compatible server written from scratch in Python, with no dependencies.
It speaks [RESP](https://redis.io/docs/latest/develop/reference/protocol-spec/),
so it works with `redis-cli`.

## Getting started

Requirements: Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```sh
./your_program.sh
```

The server listens on `localhost:6379`. From another terminal:

```sh
redis-cli PING
# PONG

redis-cli SET session abc123 EX 10
# OK

redis-cli TTL session
# (integer) 10

redis-cli INCR visits
# (integer) 1
```

## Persistence

```sh
./your_program.sh --aof appendonly.aof
```

Writes are appended to the file and replayed on startup. TTLs are stored as
absolute timestamps, so keys still expire on time after a restart. Use
`--appendfsync always|everysec|no` to choose how often it syncs to disk.

## Running tests

```sh
uv run pytest
```

## Features

- Commands: `PING`, `ECHO`, `SET`, `GET`, `DEL`, `INCR`, `DECR`, `TTL`, `PTTL`
- Concurrent clients, one thread per connection
- Atomic commands: concurrent `INCR`s never lose updates
- Binary-safe RESP parser with support for pipelining
- Key expiry (`EX`, `PX`, `EXAT`, `PXAT`)
- Append-only file persistence with crash recovery

## Project structure

```
app/
├── main.py         # TCP server and CLI options
├── commands.py     # Commands and key-value store
├── persistence.py  # Append-only file
└── resp.py         # RESP parser and encoder
tests/
```

## Roadmap

- [x] `SET`, `GET`, `DEL`
- [x] Key expiry and `TTL`
- [x] Atomic `INCR`
- [x] Binary-safe RESP parsing
- [x] Tests and CI
- [x] AOF persistence
- [ ] Benchmarks against Redis
