"""JobNova apply worker — polls API, applies to Lever jobs via Chrome CDP + extension."""

from __future__ import annotations

import sys
import time
from urllib.parse import urlparse

import httpx

from apply_job import apply_job
from chrome_launcher import (
    debug_base_url,
    ensure_chrome,
    kill_chrome_on_port,
    test_cdp_connection,
)
from config import get_config


class ApiClient:
    def __init__(self) -> None:
        cfg = get_config()
        self.base = cfg["api_url"]
        self.headers = {"X-Worker-Secret": cfg["worker_secret"]}

    def heartbeat(self, status: str = "running", message: str = "") -> None:
        try:
            httpx.post(
                f"{self.base}/applications/worker/heartbeat",
                headers=self.headers,
                json={"status": status, "message": message},
                timeout=10.0,
            )
        except Exception:
            pass

    def next_job(self) -> dict | None:
        try:
            res = httpx.get(
                f"{self.base}/applications/worker/next",
                headers=self.headers,
                timeout=15.0,
            )
            if res.status_code != 200:
                return None
            data = res.json()
            return data if data else None
        except httpx.RequestError as exc:
            print(f"[worker] API unreachable ({self.base}): {exc}", file=sys.stderr)
            return None

    def payload(self, application_id: int) -> dict:
        res = httpx.get(
            f"{self.base}/applications/{application_id}/payload",
            headers=self.headers,
            timeout=30.0,
        )
        res.raise_for_status()
        return res.json()

    def report(self, application_id: int, status: str, message: str) -> None:
        httpx.post(
            f"{self.base}/applications/worker/{application_id}/report",
            headers=self.headers,
            json={"status": status, "message": message},
            timeout=15.0,
        )


def _restart_chrome_if_needed(cfg: dict) -> None:
    if test_cdp_connection(cfg["chrome_debug_url"]):
        return
    port = urlparse(debug_base_url(cfg["chrome_debug_url"])).port or 9222
    print("[worker] CDP broken — restarting Chrome...")
    kill_chrome_on_port(port)
    ensure_chrome()


def main() -> None:
    cfg = get_config()
    if not cfg["worker_secret"]:
        print("[worker] APPLY_WORKER_SECRET is required in .env", file=sys.stderr)
        sys.exit(1)

    print("[worker] JobNova apply worker (CDP + extension, no Playwright)")

    try:
        httpx.get(f"{cfg['api_url']}/applications/worker/health", timeout=5.0)
    except httpx.RequestError:
        print(
            f"[worker] ERROR: API not running at {cfg['api_url']}. "
            "Start it first: ./run-all.sh",
            file=sys.stderr,
        )
        sys.exit(1)

    ensure_chrome()
    api = ApiClient()
    api.heartbeat("starting", "Worker ready")

    try:
        while True:
            api.heartbeat("running", "Polling for jobs")
            job = api.next_job()
            if not job:
                time.sleep(cfg["poll_interval_sec"])
                continue

            app_id = job["id"]
            print(f"[worker] Job {app_id}: {job['title']} @ {job['company']}")

            try:
                api.report(app_id, "in_progress", "Opening application form")
                payload = api.payload(app_id)
                result = apply_job(payload)
                api.report(app_id, result["status"], result["message"])
            except Exception as exc:
                err_msg = str(exc) or "Unknown worker error"
                if "403 Forbidden" in err_msg or "remote-allow-origins" in err_msg:
                    _restart_chrome_if_needed(cfg)
                    err_msg = f"{err_msg} (Chrome restarted — job will retry on next poll)"
                try:
                    api.report(app_id, "failed", err_msg)
                except Exception:
                    pass
                print(f"[worker] Failed {app_id}: {err_msg}", file=sys.stderr)

            time.sleep(3)
    except KeyboardInterrupt:
        print("[worker] Shutting down")
    finally:
        api.heartbeat("stopped", "Worker exited")


if __name__ == "__main__":
    main()
