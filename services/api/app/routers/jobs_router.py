from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobPreference, User
from app.routers.auth_router import get_current_user
from app.schemas import JobDiscoverResponse, MatchedJobResponse
from app.services.job_discovery import discover_matching_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/discover", response_model=JobDiscoverResponse)
async def discover_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = db.query(JobPreference).filter(JobPreference.user_id == user.id).first()
    if not prefs:
        raise HTTPException(
            status_code=400,
            detail="Save your job preferences before searching for jobs",
        )

    total_fetched, matched = await discover_matching_jobs(
        job_titles=prefs.job_titles or [],
        locations=prefs.locations or [],
        work_types=prefs.work_types or [],
        seniority=prefs.seniority,
    )

    return JobDiscoverResponse(
        total_fetched=total_fetched,
        total_analyzed=total_fetched,
        total_matched=len(matched),
        min_skill_match=0.0,
        jobs=[
            MatchedJobResponse(
                external_id=j.external_id,
                company=j.company,
                title=j.title,
                location=j.location,
                apply_url=j.apply_url,
                board_token=j.board_token,
                match_score=j.match_score,
                title_score=j.title_score,
                skill_score=j.skill_score,
                location_score=j.location_score,
                matched_skills=j.matched_skills,
                skill_match_details=[],
            )
            for j in matched
        ],
    )
