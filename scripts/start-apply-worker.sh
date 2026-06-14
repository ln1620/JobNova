#!/usr/bin/env bash
# Start only the apply worker (normally use ./run-all.sh for everything).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${APPLY_WORKER_SECRET:-}" ]]; then
  echo "APPLY_WORKER_SECRET is required in .env"
  exit 1
fi

WORKER_DIR="$ROOT/services/apply-worker"

if [[ ! -d "$WORKER_DIR/.venv" ]]; then
  echo "[worker] Creating virtualenv..."
  python3 -m venv "$WORKER_DIR/.venv"
  "$WORKER_DIR/.venv/bin/pip" install -q -r "$WORKER_DIR/requirements.txt"
fi

export EXTENSION_PATH="${EXTENSION_PATH:-$ROOT/extensions/auto-apply}"
export API_URL="${API_URL:-http://127.0.0.1:8000}"
export CHROME_DEBUG_URL="${CHROME_DEBUG_URL:-http://127.0.0.1:9222}"
export CHROME_PROFILE="${CHROME_PROFILE:-$WORKER_DIR/chrome-profile}"

echo "[worker] API_URL=$API_URL"
echo "[worker] EXTENSION_PATH=$EXTENSION_PATH"
exec "$WORKER_DIR/.venv/bin/python" "$WORKER_DIR/main.py"
