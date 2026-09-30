#!/bin/sh
#
# Runs the Redis server locally on port 6379.

set -e # Exit early if any commands fail

exec uv run --quiet -m app.main "$@"
