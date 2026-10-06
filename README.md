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

## Benchmarks

`redis-benchmark` with 50 clients and 100,000 requests on an Apple M2 Pro,
against Redis 8.10. Persistence off on both.

| Command | Pipeline | mini-redis | Redis |
|---|---|---|---|
| PING | 1 | ~39k req/s | ~85k req/s |
| SET | 1 | ~41k req/s | ~86k req/s |
| GET | 1 | ~41k req/s | ~88k req/s |
| PING | 16 | ~380k req/s | ~1.3M req/s |
| SET | 16 | ~250k req/s | ~1.1M req/s |
| GET | 16 | ~240k req/s | ~1.4M req/s |

Without pipelining both servers spend most of the time on network round trips,
so mini-redis is about 2x slower. With pipelining the cost per command
dominates, and Redis, written in C around an event loop, is 3-5x faster.

```sh
uv run python benchmarks/compare.py
```

## Design decisions

- **One lock for all commands.** Commands run one at a time, like in Redis, so
  each one is atomic. Without it, 8 threads doing 16,000 `INCR`s lost about
  two thirds of the updates.
- **Thread per client.** Simple and enough for this scale. Python's GIL means
  an event loop wouldn't run commands in parallel either.
- **The AOF stores state, not commands.** `SET k v EX 60` is logged as
  `SET k v PXAT <timestamp>`, so replaying it later doesn't extend the TTL.
- **Lazy and active expiry.** Expired keys are deleted when accessed, and a
  background thread removes the ones nobody reads.

## Known limitations

- One thread per connection doesn't scale to thousands of clients.
- The AOF is only compacted on startup, so it grows while the server runs.
- The expiry sweeper scans every key with a TTL; Redis samples a few instead.
- Small command set, no inline commands, no authentication. Listens on
  localhost only.

## Project structure

```
app/
├── main.py         # TCP server and CLI options
├── commands.py     # Commands and key-value store
├── persistence.py  # Append-only file
└── resp.py         # RESP parser and encoder
benchmarks/         # Comparison with Redis
tests/
```
