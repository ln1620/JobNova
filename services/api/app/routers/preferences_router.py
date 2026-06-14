from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobPreference, User
from app.routers.auth_router import get_current_user
from app.schemas import JobPreferenceResponse, JobPreferenceUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])

VALID_WORK_TYPES = {"remote", "hybrid", "onsite"}


def _to_response(pref: JobPreference) -> JobPreferenceResponse:
    return JobPreferenceResponse(
        id=pref.id,
        job_titles=pref.job_titles or [],
        locations=pref.locations or [],
        work_types=pref.work_types or [],
        seniority=pref.seniority,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


def _normalize_list(values: list[str]) -> list[str]:
    return [v.strip() for v in values if v and v.strip()]


@router.get("", response_model=JobPreferenceResponse)
def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(JobPreference).filter(JobPreference.user_id == user.id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="No job preferences saved yet")
    return _to_response(pref)


@router.put("", response_model=JobPreferenceResponse)
def update_preferences(
    body: JobPreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job_titles = _normalize_list(body.job_titles)
    locations = _normalize_list(body.locations)
    work_types = [w.lower().strip() for w in body.work_types if w and w.strip()]

    if not job_titles:
        raise HTTPException(status_code=400, detail="Add at least one target job title")
    if not locations:
        raise HTTPException(status_code=400, detail="Add at least one location")
    if not work_types:
        raise HTTPException(status_code=400, detail="Select at least one work type")

    invalid_work = [w for w in work_types if w not in VALID_WORK_TYPES]
    if invalid_work:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid work type(s): {', '.join(invalid_work)}. Use remote, hybrid, or onsite.",
        )

    seniority = body.seniority.lower().strip() if body.seniority else None
    if seniority == "":
        seniority = None
    if seniority and seniority not in {"entry", "mid", "senior"}:
        raise HTTPException(
            status_code=400,
            detail="Seniority must be entry, mid, senior, or empty",
        )

    pref = db.query(JobPreference).filter(JobPreference.user_id == user.id).first()
    if pref:
        pref.job_titles = job_titles
        pref.locations = locations
        pref.work_types = work_types
        pref.seniority = seniority
    else:
        pref = JobPreference(
            user_id=user.id,
            job_titles=job_titles,
            locations=locations,
            work_types=work_types,
            seniority=seniority,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)
    return _to_response(pref)
