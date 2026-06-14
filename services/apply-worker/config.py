"""Apply worker configuration from environment."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
load_dotenv()


@lru_cache
def get_config() -> dict:
    return {
        "api_url": os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/"),
        "worker_secret": os.getenv("APPLY_WORKER_SECRET", ""),
        "chrome_debug_url": os.getenv("CHROME_DEBUG_URL", "http://127.0.0.1:9222"),
        "extension_path": os.getenv(
            "EXTENSION_PATH",
            str(_root / "extensions" / "auto-apply"),
        ),
        "chrome_profile": os.getenv(
            "CHROME_PROFILE",
            str(_root / "services" / "apply-worker" / "chrome-profile"),
        ),
        "job_timeout_sec": int(os.getenv("JOB_TIMEOUT_SEC", "600")),
        "poll_interval_sec": int(os.getenv("POLL_INTERVAL_SEC", "5")),
        "post_submit_delay_sec": int(os.getenv("POST_SUBMIT_DELAY_SEC", "15")),
    }
