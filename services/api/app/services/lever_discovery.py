from __future__ import annotations

import asyncio
import time

import httpx

from app.data.lever_boards import LEVER_BOARDS, LEVER_JOBS_URL
from app.services.job_matcher import (
    MatchInput,
    ScoredJob,
    location_score_for_job,
    seniority_score_for_job,
    title_score_for_job,
)
from app.services.location_matcher import job_matches_user_countries

_BOARD_TIMEOUT_SEC = 10.0
_CACHE_TTL_SEC = 120
_board_cache: dict[str, tuple[float, list[tuple[dict, str, str]]]] = {}


def _lever_location(job: dict) -> str:
    categories = job.get("categories") or {}
    loc = categories.get("location") or ""
    if loc:
        return loc
    all_locs = categories.get("allLocations") or []
    if all_locs:
        return ", ".join(all_locs)
    return job.get("country") or ""


def score_lever_job(
    job: dict,
    company: str,
    slug: str,
    prefs: MatchInput,
    *,
    min_title_score: float = 0.35,
) -> ScoredJob | None:
    title = job.get("text") or ""
    apply_url = job.get("applyUrl") or ""
    job_id = job.get("id")
    if not title or not apply_url or not job_id:
        return None

    # Fast path: skip non-matching titles before location work.
    title_score = title_score_for_job(prefs.job_titles, title)
    if title_score < min_title_score:
        return None

    location = _lever_location(job)
    if not job_matches_user_countries(location, prefs.locations):
        return None

    location_score = location_score_for_job(prefs, location)
    seniority_score = seniority_score_for_job(prefs.seniority, title)

    match_score = round(
        min(0.55 * title_score + 0.35 * location_score + 0.10 * seniority_score, 1.0),
        3,
    )

    return ScoredJob(
        external_id=f"{slug}:{job_id}",
        company=company,
        title=title,
        location=location,
        apply_url=apply_url,
        board_token=slug,
        match_score=match_score,
        title_score=title_score,
        skill_score=0.0,
        location_score=location_score,
        matched_skills=[],
        skill_match_details=[],
    )


async def _fetch_lever_jobs(
    client: httpx.AsyncClient,
    slug: str,
    company: str,
) -> list[tuple[dict, str, str]]:
    now = time.time()
    cached = _board_cache.get(slug)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    url = LEVER_JOBS_URL.format(slug=slug)
    try:
        response = await client.get(url, timeout=_BOARD_TIMEOUT_SEC)
        if response.status_code != 200:
            return []
        jobs = response.json()
        if not isinstance(jobs, list):
            return []
        result = [(job, company, slug) for job in jobs]
        _board_cache[slug] = (now, result)
        return result
    except Exception:
        return []


async def fetch_all_lever_jobs() -> list[tuple[dict, str, str]]:
    async with httpx.AsyncClient(timeout=_BOARD_TIMEOUT_SEC) as client:
        tasks = [
            _fetch_lever_jobs(client, board["slug"], board["company"])
            for board in LEVER_BOARDS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    combined: list[tuple[dict, str, str]] = []
    for batch in results:
        if isinstance(batch, list):
            combined.extend(batch)
    return combined


def rank_lever_jobs(
    raw_jobs: list[tuple[dict, str, str]],
    prefs: MatchInput,
    *,
    limit: int = 30,
    min_score: float = 0.25,
    min_title_score: float = 0.35,
) -> list[ScoredJob]:
    scored: list[ScoredJob] = []
    for job, company, slug in raw_jobs:
        result = score_lever_job(
            job, company, slug, prefs, min_title_score=min_title_score
        )
        if (
            result
            and result.location_score >= 1.0
            and result.match_score >= min_score
        ):
            scored.append(result)

    scored.sort(key=lambda j: (j.match_score, j.title_score, j.location_score), reverse=True)
    return scored[:limit]
