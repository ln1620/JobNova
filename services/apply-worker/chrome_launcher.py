"""Launch and verify real Chrome with the JobNova extension (CDP, no Playwright)."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import websocket

from config import get_config

CHROME_FLAGS = (
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--disable-dev-shm-usage",
    "--disable-features=AutofillServerCommunication,AutofillEnableAccountWalletStorage",
    "--disable-autofill",
    # Required on Chrome 111+ or CDP WebSocket connections return 403.
    "--remote-allow-origins=*",
)


def _find_chrome_for_testing() -> str | None:
    """Find Playwright's bundled "Chrome for Testing" binary.

    Unlike branded Google Chrome, this build does not reject
    --load-extension / --disable-extensions-except, which is required
    for the apply-worker to load the JobNova extension.
    """
    cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
    patterns = [
        "chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-linux/chrome",
    ]
    candidates = []
    for pattern in patterns:
        candidates.extend(cache_dir.glob(pattern))
    if not candidates:
        return None
    # Prefer the highest-numbered chromium-<N> build.
    candidates.sort(key=lambda p: p.parts[len(cache_dir.parts)], reverse=True)
    return str(candidates[0])


def chrome_executable() -> str:
    cft = _find_chrome_for_testing()
    if cft:
        return cft
    for candidate in (
        "google-chrome-stable",
        "google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome-stable",
    ):
        if shutil.which(candidate):
            return candidate
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("Chrome not found (no Chrome for Testing or Google Chrome)")


def debug_base_url(debug_url: str) -> str:
    base = debug_url.rstrip("/")
    if not base.startswith("http"):
        base = f"http://{base}"
    return base


def kill_chrome_on_port(port: int) -> None:
    try:
        subprocess.run(
            ["sh", "-c", f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"],
            check=False,
        )
    except Exception:
        pass
    time.sleep(1)


def test_cdp_connection(debug_url: str) -> bool:
    """Open a test tab over CDP; returns False if WebSocket is rejected (403)."""
    base = debug_base_url(debug_url)
    tab_id = None
    try:
        res = httpx.get(f"{base}/json/version", timeout=2.0)
        if res.status_code != 200:
            return False

        res = httpx.put(f"{base}/json/new?about:blank", timeout=5.0)
        res.raise_for_status()
        info = res.json()
        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        ws = websocket.create_connection(ws_url, timeout=10)
        ws.close()
        return True
    except Exception:
        return False
    finally:
        if tab_id:
            try:
                httpx.get(f"{base}/json/close/{tab_id}", timeout=3.0)
            except Exception:
                pass


def launch_chrome() -> subprocess.Popen:
    cfg = get_config()
    debug_url = cfg["chrome_debug_url"]
    base = debug_base_url(debug_url)
    port = urlparse(base).port or 9222

    ext_path = Path(cfg["extension_path"]).resolve()
    if not ext_path.is_dir():
        raise RuntimeError(f"Extension not found: {ext_path}")

    profile = Path(cfg["chrome_profile"])
    profile.mkdir(parents=True, exist_ok=True)

    chrome_bin = chrome_executable()
    cmd = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--load-extension={ext_path}",
        f"--disable-extensions-except={ext_path}",
        f"--user-data-dir={profile}",
        *CHROME_FLAGS,
        "about:blank",
    ]
    if os.name != "nt":
        cmd.insert(1, "--no-sandbox")

    env = os.environ.copy()
    if os.getenv("DISPLAY"):
        env["DISPLAY"] = os.environ["DISPLAY"]

    print(f"[worker] Launching Chrome ({chrome_bin}) on port {port}...")
    proc = subprocess.Popen(cmd, env=env)

    for _ in range(30):
        if test_cdp_connection(debug_url):
            print("[worker] Chrome CDP ready")
            return proc
        time.sleep(1)

    proc.terminate()
    raise RuntimeError(
        "Chrome failed to start with remote debugging. "
        "Run: ./scripts/reset-apply-chrome.sh"
    )


def ensure_chrome() -> subprocess.Popen | None:
    """Ensure Chrome is running and CDP WebSocket connections work."""
    cfg = get_config()
    debug_url = cfg["chrome_debug_url"]
    port = urlparse(debug_base_url(debug_url)).port or 9222

    if test_cdp_connection(debug_url):
        print("[worker] Chrome CDP connection verified")
        return None

    print("[worker] Chrome CDP not usable — restarting Chrome...")
    kill_chrome_on_port(port)
    return launch_chrome()
