#!/bin/sh
set -e
exec uv run --quiet mini-redis "$@"
