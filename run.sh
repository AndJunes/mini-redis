#!/bin/sh
set -e
exec uv run --quiet -m app.main "$@"
