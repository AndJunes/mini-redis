# Contributing

Issues and pull requests are welcome.

## Setup

Requirements: Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest
```

## Before opening a PR

- `uv run pytest --cov=mini_redis` — tests must pass, coverage floor is 90%
- `uv run ruff check .` and `uv run ruff format .`
- `uv run mypy` — the package is typed in strict mode
- One change per PR, with commit messages in the `type(scope): summary` style
  used in the history

If you're adding a command, match real Redis behavior (replies, errors, edge
cases) and say in the PR how you checked it.
