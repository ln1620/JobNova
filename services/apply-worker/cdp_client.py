"""Chrome DevTools Protocol client — no Playwright."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
import websocket

from chrome_launcher import debug_base_url

_PAGE_FILL_JS = (
    Path(__file__).resolve().parents[2] / "extensions" / "auto-apply" / "page-fill.js"
)


class CDPSession:
    """Sync WebSocket session to a single Chrome tab."""

    def __init__(self, ws_url: str, tab_id: str, debug_base: str) -> None:
        self.ws_url = ws_url
        self.tab_id = tab_id
        self.debug_base = debug_base.rstrip("/")
        self.ws: websocket.WebSocket | None = None
        self._msg_id = 0
        self._enabled: set[str] = set()

    def connect(self) -> None:
        self.ws = websocket.create_connection(self.ws_url, timeout=120)

    def reconnect(self) -> bool:
        """Re-establish the WebSocket after Lever's submit navigation drops it.

        Returns False if the tab itself is gone (the navigation closed/replaced
        the target rather than just resetting the connection).
        """
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        try:
            tabs = httpx.get(f"{self.debug_base}/json/list", timeout=5.0).json()
        except Exception:
            return False
        for tab in tabs:
            if tab.get("id") == self.tab_id:
                self.ws_url = tab["webSocketDebuggerUrl"]
                self._enabled.clear()
                try:
                    self.connect()
                    return True
                except Exception:
                    return False
        return False

    def close(self) -> None:
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        try:
            httpx.get(f"{self.debug_base}/json/close/{self.tab_id}", timeout=5.0)
        except Exception:
            pass

    def call(self, method: str, params: dict | None = None) -> dict[str, Any]:
        if not self.ws:
            raise RuntimeError("CDP session not connected")
        self._msg_id += 1
        mid = self._msg_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result") or {}

    def enable(self, domain: str) -> None:
        if domain not in self._enabled:
            self.call(f"{domain}.enable")
            self._enabled.add(domain)

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return (result.get("result") or {}).get("value")

    def navigate(self, url: str, timeout_sec: int = 60) -> None:
        self.enable("Page")
        self.call("Page.navigate", {"url": url})
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            state = self.evaluate("document.readyState")
            if state == "complete":
                time.sleep(1)
                return
            time.sleep(0.5)
        raise TimeoutError(f"Page did not load: {url}")

    def wait_for_selector(self, selector: str, timeout_sec: int = 45) -> bool:
        deadline = time.time() + timeout_sec
        expr = f"!!document.querySelector({json.dumps(selector)})"
        while time.time() < deadline:
            if self.evaluate(expr):
                return True
            time.sleep(0.5)
        return False

    def set_file_input(self, selector: str, file_path: str) -> None:
        self.enable("DOM")
        self.enable("Page")
        doc = self.call("DOM.getDocument")
        root_id = doc["root"]["nodeId"]
        node = self.call(
            "DOM.querySelector",
            {"nodeId": root_id, "selector": selector},
        )
        node_id = node.get("nodeId")
        if not node_id:
            node = self.call(
                "DOM.querySelector",
                {"nodeId": root_id, "selector": 'input[type="file"]'},
            )
            node_id = node.get("nodeId")
        if not node_id:
            raise RuntimeError("Resume file input not found")
        self.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [file_path]})
        self.call(
            "Runtime.evaluate",
            {
                "expression": """
                (() => {
                  const el = document.querySelector('input[type="file"][name="resume"]')
                    || document.querySelector('input[type="file"]');
                  if (el) el.dispatchEvent(new Event('change', { bubbles: true }));
                })()
                """,
            },
        )

    def inject_apply_data(self, data: dict) -> None:
        payload = json.dumps(data)
        source = f"""
        (function() {{
          var p = {payload};
          document.documentElement.setAttribute("data-jobnova-payload", JSON.stringify(p));
        }})();
        """
        self.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})

    def set_dom_apply_payload(self, data: dict) -> None:
        payload = json.dumps(data)
        self.evaluate(
            f"""(() => {{
              document.documentElement.setAttribute(
                "data-jobnova-payload",
                JSON.stringify({payload})
              );
            }})()"""
        )

    def trigger_extension_fill(self) -> None:
        self.evaluate(
            """(() => {
              document.documentElement.setAttribute(
                "data-jobnova-trigger-fill",
                String(Date.now())
              );
              document.dispatchEvent(new Event("jobnova-fill"));
            })()"""
        )

    def inject_page_fill_script(self) -> None:
        if not _PAGE_FILL_JS.is_file():
            raise RuntimeError(f"page-fill.js not found at {_PAGE_FILL_JS}")
        source = _PAGE_FILL_JS.read_text(encoding="utf-8")
        self.call("Page.addScriptToEvaluateOnNewDocument", {"source": source})
        # Also inject into the current document (addScriptToEvaluateOnNewDocument
        # only runs on future navigations, not the page we're already on).
        self.call("Runtime.evaluate", {"expression": source})

    def run_page_fill_fallback(self) -> None:
        self.inject_page_fill_script()
        ready = self.evaluate(
            "typeof window.__jobnovaPageFill === 'function'"
        )
        if not ready:
            self.evaluate(
                """(() => {
                  document.documentElement.setAttribute('data-jobnova-status', 'failed');
                  document.documentElement.setAttribute(
                    'data-jobnova-message',
                    'page-fill.js failed to load'
                  );
                })()"""
            )
            return
        self.evaluate("window.__jobnovaPageFill()")

    def is_extension_ready(self) -> bool:
        return bool(
            self.evaluate(
                'document.documentElement.getAttribute("data-jobnova-ready") === "1"'
            )
        )

    def read_fill_status(self) -> dict | None:
        return self.evaluate(
            """(() => {
              const status = document.documentElement.getAttribute('data-jobnova-status');
              if (!status) return null;
              return {
                status,
                message: document.documentElement.getAttribute('data-jobnova-message') || '',
              };
            })()"""
        )


def open_tab(debug_url: str) -> CDPSession:
    base = debug_base_url(debug_url)
    res = httpx.put(f"{base}/json/new?about:blank", timeout=15.0)
    res.raise_for_status()
    info = res.json()
    session = CDPSession(info["webSocketDebuggerUrl"], info["id"], base)
    session.connect()
    return session


def wait_for_resume_parsed(session: CDPSession, timeout_sec: int = 45) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        done = session.evaluate(
            """(() => {
              const body = document.body?.innerText?.toLowerCase() || '';
              if (body.includes('success')) return true;
              const name = document.querySelector('input[name="name"]');
              return !!(name && name.value && name.value.trim());
            })()"""
        )
        if done:
            time.sleep(2)
            return
        time.sleep(1)


def wait_for_extension_ready(session: CDPSession, timeout_sec: int = 30) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if session.is_extension_ready():
            return True
        time.sleep(0.5)
    return False


def trigger_fill_with_fallback(session: CDPSession, retries: int = 3) -> None:
    """Trigger extension fill; fall back to page-context script if needed."""
    for attempt in range(retries):
        if wait_for_extension_ready(session, timeout_sec=10 if attempt == 0 else 5):
            print("[worker] Extension ready")
            break
        if attempt == 0:
            print("[worker] Waiting for extension...")

    for attempt in range(retries):
        session.trigger_extension_fill()
        time.sleep(3)
        status = session.read_fill_status()
        if status and status.get("status"):
            return
        print(f"[worker] Fill trigger attempt {attempt + 1}/{retries}")

    print("[worker] Extension did not respond — using page-fill fallback")
    session.run_page_fill_fallback()


def wait_for_submit(session: CDPSession, timeout_sec: int) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            status = session.read_fill_status()
            if status and status.get("status"):
                return {
                    "status": status["status"],
                    "message": status.get("message") or "Extension finished",
                }
            body = session.evaluate(
                "(document.body && document.body.innerText || '').toLowerCase()"
            ) or ""
            url = session.evaluate("location.href.toLowerCase()") or ""
        except (OSError, websocket.WebSocketException, RuntimeError):
            # Clicking Submit can trigger a full-page navigation that drops the
            # CDP WebSocket mid-poll. Reconnect to the same target; if the tab
            # itself is gone, the navigation almost certainly succeeded.
            if not session.reconnect():
                return {
                    "status": "submitted",
                    "message": "Application submitted (page navigated away during submit)",
                }
            time.sleep(1)
            continue
        if any(
            k in body
            for k in (
                "thank you",
                "application received",
                "thanks for applying",
                "successfully submitted",
            )
        ):
            return {"status": "submitted", "message": "Application submitted successfully"}
        if "thank" in url or "confirmation" in url:
            return {"status": "submitted", "message": "Application submitted successfully"}
        time.sleep(2)
    return {"status": "failed", "message": "Timed out waiting for form fill"}
