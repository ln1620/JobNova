"""Per-job orchestration: open a Lever application, fill it, and submit it.

The worker fills out the entire form (resume upload, profile fields, custom
questions via AI, EEO/demographics), fills any remaining required fields with
generic placeholder values, and clicks Submit. If validation errors appear,
the extension retries the fill/submit once before reporting "failed". The
final status ("submitted" or "failed") is reported back via wait_for_submit.
"""

from __future__ import annotations

import time

from cdp_client import (
    open_tab,
    trigger_fill_with_fallback,
    wait_for_submit,
)
from config import get_config


def apply_job(payload: dict) -> dict:
    cfg = get_config()
    session = open_tab(cfg["chrome_debug_url"])
    try:
        dom_payload = {
            "application_id": payload["application_id"],
            "email": payload["email"],
            "display_name": payload.get("display_name"),
            "company": payload["company"],
            "title": payload["title"],
            "parsed_json": payload.get("parsed_json") or {},
            "application_answers": payload.get("application_answers") or {},
            "access_token": payload["access_token"],
            "worker_secret": cfg["worker_secret"],
            "api_url": cfg["api_url"],
        }

        # Make the payload available to the content script as soon as the
        # page (and any future navigation) loads.
        session.inject_apply_data(dom_payload)

        session.navigate(payload["apply_url"])

        if not session.wait_for_selector("form.applications-form, form", timeout_sec=45):
            return {"status": "failed", "message": "Lever application form did not load"}

        # Ensure the payload is set on the document we're currently on too
        # (addScriptToEvaluateOnNewDocument only applies to future loads).
        session.set_dom_apply_payload(dom_payload)

        resume_path = payload.get("resume_path")
        if resume_path:
            try:
                session.set_file_input('input[type="file"][name="resume"]', resume_path)
            except Exception as exc:
                print(f"[worker] resume upload failed: {exc}")

        trigger_fill_with_fallback(session)

        result = wait_for_submit(session, cfg["job_timeout_sec"])

        
        delay = cfg["post_submit_delay_sec"]
        if delay > 0:
            print(f"[worker] {result['status']} — leaving tab open for {delay}s")
            time.sleep(delay)

        return result
    finally:
        session.close()
