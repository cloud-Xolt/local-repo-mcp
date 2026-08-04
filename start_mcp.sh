#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 bootstrap.py
exec .venv/bin/python launch_mcp.py
