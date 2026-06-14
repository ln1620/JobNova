import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import get_settings

ATS_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "jobvite.com",
    "icims.com",
    "taleo.net",
)

URL_IN_TEXT = re.compile(r"https?://[^\s\)\]>\,\"']+", re.I)


def _job_sort_score(raw: dict) -> int:
    """Prefer postings that already include a direct company/ATS apply link."""
    score = 0
    if raw.get("external_apply_url"):
        score += 20
    st = (raw.get("source_type") or "").lower()
    sd = (raw.get("source_domain") or "").lower()
    if st == "ats":
        score += 15
    if sd and "linkedin.com" not in sd:
        score += 10
    lou = (raw.get("linkedin_org_url") or "").lower()
    if lou.startswith("http") and "linkedin.com" not in lou:
        score += 8
    return score


def extract_urls_from_description(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for m in URL_IN_TEXT.findall(text):
        u = m.rstrip(".,;)")
        if u.startswith("http") and u not in found:
            found.append(u)
    return found


class RapidAPIRateLimitError(Exception):
    """RapidAPI returned HTTP 429 — wait and retry or upgrade plan."""


def load_sample_jobs(limit: int) -> list[dict]:
    root = Path(__file__).resolve().parents[4]
    path = root / "fixtures" / "linkedin_sample.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data[:limit]


async def search_linkedin_jobs(query: str, location: str, limit: int) -> list[dict]:
    settings = get_settings()
    if not settings.rapidapi_key:
        raise ValueError("RAPIDAPI_KEY is not set in .env")

    url = f"https://{settings.rapidapi_host}{settings.rapidapi_search_path}"
    headers = {
        "x-rapidapi-key": settings.rapidapi_key,
        "x-rapidapi-host": settings.rapidapi_host,
    }
    params = {
        "offset": "0",
        "title_filter": query,
        "location_filter": location,
        "description_type": "text",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = None
        for attempt in range(4):
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 429:
                if attempt < 3:
                    await asyncio.sleep(2**attempt + 2)
                    continue
                raise RapidAPIRateLimitError(
                    "RapidAPI rate limit (429). Wait 1–2 minutes and try again, "
                    "or check your plan at rapidapi.com."
                )
            break
        assert response is not None
        response.raise_for_status()
        data = response.json()

    jobs: list[dict] = []
    if isinstance(data, list):
        jobs = data
    elif isinstance(data, dict):
        for key in ("data", "jobs", "results", "items"):
            if key in data and isinstance(data[key], list):
                jobs = data[key]
                break

    jobs.sort(key=_job_sort_score, reverse=True)
    return jobs[:limit]


def normalize_job(raw: dict) -> dict:
    org = raw.get("organization") or raw.get("company_name") or raw.get("company") or "Unknown"
    org_url = (
        raw.get("organization_url")
        or raw.get("linkedin_org_url")
        or raw.get("company_url")
        or ""
    )
    job_url = raw.get("url") or raw.get("job_url") or raw.get("link") or ""
    external_apply = (raw.get("external_apply_url") or "").strip()
    source_domain = (raw.get("source_domain") or "").strip().lower()
    source_type = (raw.get("source_type") or "").strip().lower()
    slug = (raw.get("linkedin_org_slug") or "").strip()

    website = (
        raw.get("company_website")
        or raw.get("organization_website")
        or raw.get("website")
        or ""
    )
    linkedin_org_site = (raw.get("linkedin_org_url") or "").strip()
    if linkedin_org_site.startswith("http") and "linkedin.com" not in linkedin_org_site.lower():
        website = website or linkedin_org_site

    if website and not website.startswith("http"):
        website = f"https://{website}"

    description_urls = extract_urls_from_description(raw.get("description_text") or "")

    return {
        "organization": org,
        "organization_url": org_url,
        "url": job_url,
        "company_website": website,
        "title": raw.get("title") or "",
        "external_apply_url": external_apply,
        "source_domain": source_domain,
        "source_type": source_type,
        "linkedin_org_slug": slug,
        "description_urls": description_urls,
        "_raw": raw,
    }
