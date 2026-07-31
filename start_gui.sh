#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python run_gui.py
fi
exec python3 run_gui.py
