#!/bin/sh
set -e
exec uv run --quiet -m mini_redis.main "$@"
