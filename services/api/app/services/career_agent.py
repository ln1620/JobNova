from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.async_api import async_playwright

from app.config import get_settings
from app.services.linkedin import ATS_DOMAINS, extract_urls_from_description

CAREER_HINTS = re.compile(
    r"career|careers|jobs|job-openings|join-us|work-with-us|hiring|opportunities|vacancies",
    re.I,
)
JOB_HINTS = re.compile(
    r"apply|view.job|opening|position|role|lever\.co|greenhouse\.io|workday|ashby|job-details|/jobs/",
    re.I,
)
BLOCKED_HOSTS = (
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "google.com",
    "google.co",
    "goo.gl",
    "maps.google",
    "googleusercontent.com",
    "bing.com",
    "duckduckgo.com",
    "wikipedia.org",
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _is_blocked(url: str) -> bool:
    if not url:
        return True
    low = url.lower()
    if "/maps" in low or "google.com/maps" in low:
        return True
    h = _host(url)
    return not h or any(b in h for b in BLOCKED_HOSTS)


def _clean_url(url: str) -> Optional[str]:
    if not url or not url.startswith("http"):
        return None
    if _is_blocked(url):
        return None
    return url.split("?")[0].rstrip("/")


def _domain_to_url(domain: str) -> Optional[str]:
    domain = domain.strip().lower()
    if not domain or _is_blocked(f"https://{domain}"):
        return None
    if domain.startswith("http"):
        return _clean_url(domain)
    return _clean_url(f"https://{domain}")


async def _url_exists(url: str) -> bool:
    final = await _resolve_final_url(url)
    return final is not None


async def _resolve_final_url(url: str) -> Optional[str]:
    """Follow redirects and reject Google Maps / blocked hosts."""
    cleaned = _clean_url(url)
    if not cleaned or _is_blocked(cleaned):
        return None
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            r = await client.get(cleaned)
            final = _clean_url(str(r.url))
            if final and not _is_blocked(final):
                return final
    except Exception:
        pass
    return cleaned if not _is_blocked(cleaned) else None


async def _website_from_duckduckgo(company_name: str) -> Optional[str]:
    """Lightweight fallback when slug guessing fails."""
    if not company_name:
        return None
    query = f"{company_name} official company website"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "JobNova/1.0"},
            )
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a.result__a"):
            href = a.get("href") or ""
            if href.startswith("http") and not _is_blocked(href):
                resolved = await _resolve_final_url(href)
                if resolved:
                    return resolved
    except Exception:
        return None
    return None


async def _website_from_linkedin_company_page(company_url: str) -> Optional[str]:
    if not company_url or "linkedin.com/company" not in company_url:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(company_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                for selector in (
                    'a[href^="http"][data-tracking-control-name="about_website"]',
                    'a[href^="http"].link-without-visited-state',
                ):
                    el = await page.query_selector(selector)
                    if el:
                        href = await el.get_attribute("href")
                        if href and not _is_blocked(href):
                            return await _resolve_final_url(href)
                html = await page.content()
                for match in re.findall(r'"sameAs"\s*:\s*"(https?://[^"]+)"', html):
                    if not _is_blocked(match):
                        return await _resolve_final_url(match)
            finally:
                await browser.close()
    except Exception:
        return None
    return None


async def resolve_company_website_from_slug(slug: str, company_name: str) -> Optional[str]:
    if not slug:
        slug = re.sub(r"[^a-z0-9-]", "", company_name.lower().replace(" ", "-"))[:40]
    if not slug:
        return None

    compact = slug.replace("-", "")
    candidates = [
        f"https://www.{compact}.com",
        f"https://{compact}.com",
        f"https://www.{slug}.com",
        f"https://{slug}.com",
        f"https://www.{compact}.io",
        f"https://www.{compact}.co",
    ]
    # Remove duplicate candidates
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    for url in unique:
        resolved = await _resolve_final_url(url)
        if resolved:
            return resolved
    return None


def resolve_from_rapidapi_fields(job: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Use Fantastic Jobs API fields first (most reliable).
    Returns: company_website, career_page_url, open_position_url
    """
    external = _clean_url(job.get("external_apply_url") or "")
    source_domain = (job.get("source_domain") or "").strip().lower()
    source_type = (job.get("source_type") or "").strip().lower()
    slug = job.get("linkedin_org_slug") or ""
    org_name = job.get("organization") or ""

    opening: Optional[str] = None
    career: Optional[str] = None
    website: Optional[str] = _clean_url(job.get("company_website") or "")

    for desc_url in job.get("description_urls") or []:
        u = _clean_url(desc_url)
        if not u or _is_blocked(u):
            continue
        if any(ats in _host(u) for ats in ATS_DOMAINS) or CAREER_HINTS.search(u):
            career = career or u
            opening = opening or u
        elif not website:
            website = u

    # Best opening: direct external apply URL (Lever, Greenhouse, company site)
    if external and "linkedin.com" not in external:
        opening = external
        host = _host(external)
        if any(ats in host for ats in ATS_DOMAINS):
            career = career or _domain_to_url(host)
            if "jobs." in host or "boards." in host:
                # e.g. jobs.lever.co — company site still from slug
                pass
        elif not website:
            website = f"https://{host}"

    # Career site from API source_domain (ATS or career-site)
    if source_domain and "linkedin.com" not in source_domain:
        sd_url = _domain_to_url(source_domain)
        if sd_url:
            if source_type == "ats" or any(ats in source_domain for ats in ATS_DOMAINS):
                career = career or sd_url
                if opening and _host(opening) == _host(sd_url):
                    pass  # opening already set
            else:
                career = career or sd_url
                if not website:
                    website = sd_url

    return website, career, opening


def extract_links(html: str, base_url: str, max_links: int = 60) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    links: list[dict] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        if full in seen or _is_blocked(full):
            continue
        seen.add(full)
        text = (a.get_text() or "").strip()[:120]
        links.append({"url": full, "text": text})
        if len(links) >= max_links:
            break
    return links


def heuristic_career_url(links: list[dict], website: str) -> Optional[str]:
    for link in links:
        u = link["url"]
        if CAREER_HINTS.search(link["text"]) or CAREER_HINTS.search(u):
            if not _is_blocked(u):
                return _clean_url(u)
    return None


def heuristic_job_url(links: list[dict], career_url: str) -> Optional[str]:
    scored: list[tuple[int, str]] = []
    for link in links:
        u = link["url"]
        if _is_blocked(u) or "linkedin.com" in u:
            continue
        score = 0
        if JOB_HINTS.search(link["text"]) or JOB_HINTS.search(u):
            score += 3
        if any(ats in u for ats in ATS_DOMAINS):
            score += 5
        if "/job" in u.lower() or "/position" in u.lower() or "/opening" in u.lower():
            score += 2
        if score > 0:
            scored.append((score, u))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return _clean_url(scored[0][1])
    return None


def career_path_candidates(website: str) -> list[str]:
    base = website.rstrip("/")
    return [base + p for p in ("/careers", "/career", "/jobs", "/job", "/join-us", "/work-with-us")]


def llm_pick_url(task: str, page_url: str, links: list[dict]) -> Optional[str]:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Pick the best URL for the task. Never pick linkedin.com, google.com, or maps. "
                        'JSON only: {"url": "..."} or {"url": null}.'
                    ),
                },
                {"role": "user", "content": json.dumps({"task": task, "page_url": page_url, "links": links[:35]})},
            ],
            temperature=0,
        )
        text = resp.choices[0].message.content or ""
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        return _clean_url(data.get("url") or "")
    except Exception:
        return None


async def _career_via_http_paths(website: str) -> Optional[str]:
    for path in career_path_candidates(website):
        resolved = await _resolve_final_url(path)
        if resolved:
            return resolved
    return None


async def _browse_career_on_website(website: str) -> Optional[str]:
    fast = await _career_via_http_paths(website)
    if fast:
        return fast
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(website, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(400)
                html = await page.content()
                links = extract_links(html, website)
                career = heuristic_career_url(links, website)
                if career:
                    return career
                for path in career_path_candidates(website):
                    try:
                        resp = await page.goto(path, wait_until="domcontentloaded", timeout=10000)
                        if resp and resp.status < 400:
                            final = _clean_url(page.url)
                            if final and not _is_blocked(final):
                                return final
                    except Exception:
                        continue
                return llm_pick_url("careers or jobs page", website, links)
            finally:
                await browser.close()
    except Exception:
        return None


async def _browse_opening_on_career(career: str, company_site: str) -> Optional[str]:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(career, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(400)
                html = await page.content()
                links = extract_links(html, career)
                opening = heuristic_job_url(links, career)
                if opening:
                    return opening
                return llm_pick_url("one job posting apply link on careers site", career, links)
            finally:
                await browser.close()
    except Exception:
        return None


async def find_career_and_opening(
    company_name: str,
    company_website: Optional[str],
    linkedin_company_url: Optional[str],
    job: Optional[dict] = None,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    1) RapidAPI fields (external_apply_url, source_domain)
    2) Resolve company website from slug (never scrape random LinkedIn links)
    3) Playwright web agent on company site → career → opening
    """
    job = job or {}
    website, career, opening = resolve_from_rapidapi_fields(job)

    if not website:
        website = await resolve_company_website_from_slug(
            job.get("linkedin_org_slug") or "",
            company_name,
        )

    if not website and linkedin_company_url:
        website = await _website_from_linkedin_company_page(linkedin_company_url)

    if not website:
        website = await _website_from_duckduckgo(company_name)

    if website:
        website = await _resolve_final_url(website)

    if not website:
        return None, career, opening, "Could not resolve company website URL"

    if career and opening:
        return website, career, opening, None

    # If we have career but no opening, browse career page
    if career and not opening:
        opening = await _browse_opening_on_career(career, website)
        if opening and "linkedin.com" in opening:
            opening = None

    # If no career page yet, browse company website
    if not career:
        career = await _career_via_http_paths(website) or await _browse_career_on_website(website)
        if career:
            opening = opening or await _browse_opening_on_career(career, website)

    if career and "linkedin.com" in career:
        career = None

    if opening and "linkedin.com" in opening:
        opening = None

    if not career:
        return website, None, opening, "Career page not found on company website"
    if not opening:
        return website, career, None, "No opening position URL found on career page"

    return website, career, opening, None
