from __future__ import annotations

import html
import re


def jd_html_to_text(content: str) -> str:
    if not content:
        return ""
    text = html.unescape(content)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10000]
