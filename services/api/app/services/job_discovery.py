from __future__ import annotations

from app.services.job_matcher import MatchInput
from app.services.lever_discovery import fetch_all_lever_jobs, rank_lever_jobs


async def discover_matching_jobs(
    job_titles: list[str],
    locations: list[str],
    work_types: list[str],
    seniority: str | None,
    skills: list[str] | None = None,
) -> tuple[int, list]:
    prefs = MatchInput(
        job_titles=job_titles,
        locations=locations,
        work_types=work_types,
        seniority=seniority,
        skills=skills or [],
    )

    raw_jobs = await fetch_all_lever_jobs()
    matched = rank_lever_jobs(raw_jobs, prefs, limit=30, min_score=0.05)
    return len(raw_jobs), matched
