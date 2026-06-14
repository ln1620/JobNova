#!/usr/bin/env bash
# Stop worker Chrome and clear profile so CDP starts with correct flags.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CHROME_DEBUG_PORT:-9222}"

echo "[reset] Stopping Chrome on port ${PORT}..."
lsof -ti:"${PORT}" 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Also stop Chrome processes using the worker profile.
PROFILE="$ROOT/services/apply-worker/chrome-profile"
if [[ -d "$PROFILE" ]]; then
  pkill -f "user-data-dir=${PROFILE}" 2>/dev/null || true
  sleep 1
  echo "[reset] Removing Chrome profile at $PROFILE"
  rm -rf "$PROFILE"
fi

echo "[reset] Done. Start worker: ./scripts/start-apply-worker.sh"
