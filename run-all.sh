#!/usr/bin/env bash
# Start everything in one terminal: API + web + interview agent + apply worker + Chrome.
# Press Ctrl+C to stop all services.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log() { printf '\033[1;36m[jobnova]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[jobnova]\033[0m %s\n' "$*"; }

cleanup() {
  log "Stopping all services..."
  lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
  lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
  lsof -ti:9222 2>/dev/null | xargs kill -9 2>/dev/null || true
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "agents/interview.*main.py dev" 2>/dev/null || true
  pkill -f "next dev" 2>/dev/null || true
  pkill -f "services/apply-worker/main.py" 2>/dev/null || true
  pkill -f "user-data-dir=${ROOT}/services/apply-worker/chrome-profile" 2>/dev/null || true
  exit 0
}
trap cleanup EXIT INT TERM

prefix() {
  local tag=$1
  while IFS= read -r line || [[ -n "$line" ]]; do
    printf '[%s] %s\n' "$tag" "$line"
  done
}

wait_for_api() {
  local i
  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:8000/applications/worker/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  err "API did not start on port 8000"
  exit 1
}

wait_for_apply_worker() {
  local i status
  for i in $(seq 1 30); do
    status=$(curl -sf "http://127.0.0.1:8000/applications/worker/health" 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [[ "$status" == "running" || "$status" == "starting" ]]; then
      log "Apply worker reported in (status: $status)"
      return 0
    fi
    sleep 1
  done
  log "WARNING: apply worker did not report in — check Chrome install / extension path / apply-worker logs above"
}

ensure_web_deps() {
  local web="$ROOT/apps/web"

  if [[ ! -f "$web/node_modules/next/dist/server/next.js" ]]; then
    log "Installing web dependencies..."
    (cd "$web" && npm install --no-audit --no-fund)
  fi
}

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
  log "Loaded .env"
else
  err "No .env — run: cp .env.example .env and add your keys"
  exit 1
fi

if [[ -z "${APPLY_WORKER_SECRET:-}" ]]; then
  err "APPLY_WORKER_SECRET is required in .env"
  exit 1
fi

for port in 8000 3000 9222; do
  if lsof -ti:"$port" >/dev/null 2>&1; then
    log "Port $port busy — stopping old process..."
    lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
done

# --- API (FastAPI) ---
(
  cd "$ROOT/services/api"
  PY="${PY:-python3}"
  if [[ ! -d .venv ]]; then
    log "Creating API virtualenv (first run)..."
    "$PY" -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
  fi
  if ! .venv/bin/python -c "from app.main import app" 2>/dev/null; then
    log "Repairing API virtualenv (one-time)..."
    .venv/bin/pip install -q -r requirements.txt
  fi
  exec .venv/bin/python -m uvicorn app.main:app --port 8000
) 2>&1 | prefix "api" &

wait_for_api

# --- LiveKit interview agent (Python 3.10+) ---
AGENT_PY=""
for candidate in python3.12 python3.11 python3.10; do
  if command -v "$candidate" &>/dev/null; then
    AGENT_PY=$candidate
    break
  fi
done
if [[ -z "$AGENT_PY" ]]; then
  err "Need Python 3.10+ for interview agent (brew install python@3.11)"
  exit 1
fi

(
  cd "$ROOT/agents/interview"
  if [[ ! -d .venv ]]; then
    log "Creating agent virtualenv (first run)..."
    "$AGENT_PY" -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q -r requirements.txt
  else
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  exec "$AGENT_PY" main.py dev
) 2>&1 | prefix "agent" &

# --- Next.js web ---
ensure_web_deps
(
  cd "$ROOT/apps/web"
  exec npm run dev
) 2>&1 | prefix "web" &

# --- Apply worker (Chrome CDP + extension) ---
WORKER_DIR="$ROOT/services/apply-worker"
(
  cd "$WORKER_DIR"
  if [[ ! -d .venv ]]; then
    log "Creating apply-worker virtualenv (first run)..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
  fi
  export EXTENSION_PATH="${EXTENSION_PATH:-$ROOT/extensions/auto-apply}"
  export API_URL="${API_URL:-http://127.0.0.1:8000}"
  export CHROME_DEBUG_URL="${CHROME_DEBUG_URL:-http://127.0.0.1:9222}"
  export CHROME_PROFILE="${CHROME_PROFILE:-$WORKER_DIR/chrome-profile}"
  exec .venv/bin/python main.py
) 2>&1 | prefix "worker" &

wait_for_apply_worker

log ""
log "All services started in this terminal:"
log "  Web app       → http://localhost:3000"
log "  API docs      → http://localhost:8000/docs"
log "  Interview     → LiveKit agent"
log "  Auto-apply    → Chrome worker (port 9222)"
log ""
log "Open http://localhost:3000 — complete profile, find jobs, click Start auto-apply."
log "Press Ctrl+C to stop everything."
log ""

wait
