#!/bin/bash
# LiveKit agents require Python 3.10+
set -e
cd "$(dirname "$0")"

PY=""
for candidate in python3.12 python3.11 python3.10; do
  if command -v "$candidate" &>/dev/null; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "ERROR: Install Python 3.10+ (brew install python@3.11)"
  exit 1
fi

echo "Using $PY ($($PY --version))"

# Load secrets from project root .env
if [ -f ../../.env ]; then
  set -a
  # shellcheck disable=SC1091
  source ../../.env
  set +a
  echo "Loaded ../../.env"
fi

if [ ! -d .venv ]; then
  $PY -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
exec $PY main.py dev
