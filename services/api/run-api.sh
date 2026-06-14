#!/bin/bash
# Start FastAPI — uses the local venv (no need for `uvicorn` on your global PATH).
set -e
cd "$(dirname "$0")"

if [ -f ../../.env ]; then
  set -a
  # shellcheck disable=SC1091
  source ../../.env
  set +a
  echo "Loaded ../../.env"
fi

PY="${PY:-python3}"
if ! command -v "$PY" &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.9+ or set PY=python3.11"
  exit 1
fi

echo "Using $($PY --version)"

if [ ! -d .venv ]; then
  echo "Creating virtualenv in services/api/.venv ..."
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

PORT="${PORT:-8000}"
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "ERROR: Port $PORT is already in use (old API still running)."
  echo "Stop it with:  kill \$(lsof -ti:$PORT)"
  echo "Or use another port:  PORT=8001 ./run-api.sh"
  exit 1
fi

echo "Starting API on http://localhost:$PORT"
exec .venv/bin/python -m uvicorn app.main:app --reload --reload-dir app --port "$PORT"
