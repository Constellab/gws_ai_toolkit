#!/usr/bin/env bash
# PROTOTYPE — one command to run the LanceDB spike. Throwaway.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"

if [ ! -d "$VENV" ]; then
  echo "== creating isolated venv =="
  # uv, not python -m venv: this image has no ensurepip.
  # NOT --system-site-packages: `python3` here is itself the lab venv, so that flag
  # inherits the BASE interpreter's packages, not the lab's — pandas goes missing and
  # pyarrow floats. Pin the two gws_core constraints explicitly instead. Doing so IS the
  # pin check the plan asks for: if lancedb cannot sit on pyarrow 24.0.0 / pandas 2.3.3,
  # that is a settings.json conflict and we need to know now.
  uv venv --python python3 "$VENV"
  echo "== installing lancedb + llama-index against gws_core's real pins =="
  VIRTUAL_ENV="$VENV" uv pip install \
    "pyarrow==24.0.0" \
    "pandas==2.3.3" \
    "lancedb" \
    "llama-index-core>=0.13,<0.15" \
    "llama-index-vector-stores-lancedb"
fi

echo
"$VENV/bin/python" spike.py
