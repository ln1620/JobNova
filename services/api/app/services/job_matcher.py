from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.location_matcher import job_matches_user_countries, location_match_score

STOP_WORDS = {
    "a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to", "with",
    "level", "ii", "iii", "iv", "us", "usa",
}


@dataclass
class MatchInput:
    job_titles: list[str]
    locations: list[str]
    work_types: list[str]
    seniority: str | None
    skills: list[str] = field(default_factory=list)


@dataclass
class ScoredJob:
    external_id: str
    company: str
    title: str
    location: str
    apply_url: str
    board_token: str
    match_score: float
    title_score: float
    skill_score: float
    location_score: float
    matched_skills: list[str] = field(default_factory=list)
    skill_match_details: list = field(default_factory=list)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9+#.]+", _normalize(text))
    return {w for w in words if len(w) > 1 and w not in STOP_WORDS}


def _overlap_score(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _substring_match(needles: list[str], haystack: str) -> float:
    hay = _normalize(haystack)
    best = 0.0
    for needle in needles:
        n = _normalize(needle)
        if not n:
            continue
        if n in hay:
            best = max(best, 1.0)
            continue
        score = _overlap_score(n, hay)
        best = max(best, score)
    return best


def title_score_for_job(job_titles: list[str], job_title: str) -> float:
    score = round(_substring_match(job_titles, job_title), 3)
    hay = _normalize(job_title)
    weak_role_words = {
        "engineer", "developer", "scientist", "analyst", "manager",
        "lead", "staff", "senior", "junior", "intern", "ii", "iii",
    }
    for needle in job_titles:
        n = _normalize(needle)
        if not n:
            continue
        keywords = [w for w in _tokens(n) if w not in weak_role_words]
        if keywords and not any(w in hay for w in keywords):
            score = min(score, 0.15)
    return round(score, 3)


def location_score_for_job(prefs: MatchInput, job_location: str) -> float:
    """Strict country match only — 100% or excluded."""
    if not job_matches_user_countries(job_location, prefs.locations):
        return 0.0

    loc = _normalize(job_location)
    score = location_match_score(job_location, prefs.locations)

    if prefs.work_types:
        if "remote" in prefs.work_types and "remote" in loc:
            pass  # already country-filtered
        if "hybrid" in prefs.work_types and "hybrid" in loc:
            pass
        if "onsite" in prefs.work_types and "remote" not in loc and "hybrid" not in loc:
            pass

    return score


def seniority_score_for_job(seniority: str | None, job_title: str) -> float:
    if not seniority:
        return 0.5
    title = _normalize(job_title)
    if seniority == "entry" and any(k in title for k in ("intern", "junior", "entry", "associate")):
        return 1.0
    if seniority == "senior" and any(k in title for k in ("senior", "staff", "principal", "lead")):
        return 1.0
    if seniority == "mid" and not any(k in title for k in ("intern", "junior", "staff", "principal")):
        return 0.7
    return 0.3


def score_job_by_preferences(
    job: dict,
    company: str,
    board_token: str,
    prefs: MatchInput,
) -> ScoredJob | None:
    title = job.get("title") or ""
    location = (job.get("location") or {}).get("name") or ""
    apply_url = (job.get("absolute_url") or "").replace(
        "boards.greenhouse.io", "job-boards.greenhouse.io"
    )
    job_id = job.get("id")
    if not title or not apply_url or job_id is None:
        return None

    if not job_matches_user_countries(location, prefs.locations):
        return None

    title_score = title_score_for_job(prefs.job_titles, title)
    location_score = location_score_for_job(prefs, location)
    seniority_score = seniority_score_for_job(prefs.seniority, title)

    match_score = round(
        min(0.55 * title_score + 0.35 * location_score + 0.10 * seniority_score, 1.0),
        3,
    )

    return ScoredJob(
        external_id=f"{board_token}:{job_id}",
        company=job.get("company_name") or company,
        title=title,
        location=location,
        apply_url=apply_url,
        board_token=board_token,
        match_score=match_score,
        title_score=title_score,
        skill_score=0.0,
        location_score=location_score,
        matched_skills=[],
        skill_match_details=[],
    )


def rank_jobs_by_preferences(
    raw_jobs: list[tuple[dict, str, str]],
    prefs: MatchInput,
    *,
    limit: int = 30,
    min_score: float = 0.10,
) -> list[ScoredJob]:
    scored: list[ScoredJob] = []
    for job, company, board_token in raw_jobs:
        result = score_job_by_preferences(job, company, board_token, prefs)
        if result and result.location_score >= 1.0 and result.match_score >= min_score:
            scored.append(result)

    scored.sort(key=lambda j: (j.match_score, j.title_score, j.location_score), reverse=True)
    return scored[:limit]
