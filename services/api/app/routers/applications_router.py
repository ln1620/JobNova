from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.database import get_db
from app.models import Application, ApplicationAnswers, Resume, User
from app.routers.auth_router import get_current_user
from app.schemas import (
    AnswerQuestionRequest,
    AnswerQuestionResponse,
    ApplicationAnswersData,
    ApplicationAnswersResponse,
    ApplicationQueueRequest,
    ApplicationQueueResponse,
    ApplicationReportRequest,
    ApplicationResponse,
    ApplyPayloadResponse,
    ApplyProfileResponse,
    ParsedProfile,
    WorkerHeartbeatRequest,
)
from app.services.application_answers import generate_text_answer
from app.worker_auth import (
    get_application_for_worker,
    get_user_for_application,
    verify_worker_secret,
)

router = APIRouter(prefix="/applications", tags=["applications"])

VALID_STATUSES = {"queued", "in_progress", "submitted", "failed", "blocked"}
REPORT_STATUSES = {"submitted", "failed", "blocked", "in_progress"}

_worker_heartbeat: dict = {
    "at": None,
    "status": "unknown",
    "message": "",
    "apply_enabled": False,
}

_worker_apply_enabled: bool = False
_worker_apply_user_id: int | None = None


def _disable_auto_apply() -> None:
    global _worker_apply_enabled, _worker_apply_user_id
    _worker_apply_enabled = False
    _worker_apply_user_id = None
    _worker_heartbeat["apply_enabled"] = False


def _enable_auto_apply(user_id: int) -> None:
    global _worker_apply_enabled, _worker_apply_user_id
    _worker_apply_enabled = True
    _worker_apply_user_id = user_id
    _worker_heartbeat["apply_enabled"] = True


def _maybe_disable_auto_apply(db: Session) -> None:
    global _worker_apply_enabled, _worker_apply_user_id
    if _worker_apply_user_id is None:
        _disable_auto_apply()
        return
    pending = (
        db.query(Application)
        .filter(
            Application.user_id == _worker_apply_user_id,
            Application.status.in_(["queued", "in_progress"]),
        )
        .count()
    )
    if pending == 0:
        _disable_auto_apply()


@router.post("/stop-auto-apply")
def stop_auto_apply(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop worker until user clicks Start auto-apply again."""
    in_progress = (
        db.query(Application)
        .filter(Application.user_id == user.id, Application.status == "in_progress")
        .all()
    )
    for app in in_progress:
        app.status = "failed"
        app.message = "Stopped — click Start auto-apply when ready"
    if in_progress:
        db.commit()
    _disable_auto_apply()
    return {"ok": True, "stopped": len(in_progress)}


@router.post("/clear-queued")
def clear_queued_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove stale queued jobs so a fresh search can be applied."""
    queued = (
        db.query(Application)
        .filter(Application.user_id == user.id, Application.status == "queued")
        .all()
    )
    for app in queued:
        app.status = "failed"
        app.message = "Cleared — re-run job search and Start auto-apply"
    if queued:
        db.commit()
    _disable_auto_apply()
    return {"cleared": len(queued)}


def _is_lever_url(url: str) -> bool:
    return "lever.co" in (url or "").lower()


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _release_stale_in_progress(db: Session) -> None:
    """Unblock the worker when old Greenhouse or timed-out jobs are stuck."""
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=15)
    changed = False

    for app in db.query(Application).filter(Application.status == "in_progress").all():
        release = False
        if not _is_lever_url(app.apply_url):
            app.status = "failed"
            app.message = "Skipped — not a Lever application"
            release = True
        else:
            updated = _as_utc(app.updated_at)
            if updated and updated < stale_cutoff:
                app.status = "failed"
                app.message = "Timed out — worker reset stale job"
                release = True
        if release:
            changed = True

    if changed:
        db.commit()


def _resume_mime(file_type: str) -> str:
    if file_type == "pdf":
        return "application/pdf"
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _stage_resume_for_worker(resume: Resume, application_id: int) -> tuple[str, str]:
    src = Path(resume.file_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")
    dest_dir = Path("/tmp/jobnova-resumes")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{application_id}_{resume.original_filename}"
    shutil.copy2(src, dest)
    return str(dest), resume.original_filename


@router.post("/queue", response_model=ApplicationQueueResponse)
def queue_applications(
    body: ApplicationQueueRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent is required to start auto-apply")
    if not body.jobs:
        raise HTTPException(status_code=400, detail="No jobs to queue")

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=400, detail="Upload your resume before auto-applying")

    answers = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()
    if not answers or not answers.city.strip() or not answers.phone.strip():
        raise HTTPException(
            status_code=400,
            detail="Complete Application Answers (city, phone, demographics) before auto-applying",
        )

    created: list[Application] = []
    for job in body.jobs[:15]:
        if not _is_lever_url(job.apply_url):
            continue

        existing = (
            db.query(Application)
            .filter(
                Application.user_id == user.id,
                Application.external_job_id == job.external_id,
                Application.status.in_(["queued", "in_progress", "submitted", "blocked"]),
            )
            .first()
        )
        if existing:
            continue

        app = Application(
            user_id=user.id,
            external_job_id=job.external_id,
            company=job.company,
            title=job.title,
            location=job.location,
            apply_url=job.apply_url,
            status="queued",
        )
        db.add(app)
        created.append(app)

    if not created:
        lever_jobs = [j for j in body.jobs[:15] if _is_lever_url(j.apply_url)]
        if not lever_jobs:
            raise HTTPException(
                status_code=400,
                detail="No Lever apply URLs in selection. Re-run job search.",
            )
        pending = (
            db.query(Application)
            .filter(
                Application.user_id == user.id,
                Application.status == "queued",
            )
            .order_by(Application.created_at.asc())
            .all()
        )
        pending = [a for a in pending if _is_lever_url(a.apply_url)]
        if pending:
            _enable_auto_apply(user.id)
            return ApplicationQueueResponse(
                queued=0,
                resumed=True,
                applications=[ApplicationResponse.model_validate(a) for a in pending[:15]],
            )
        raise HTTPException(
            status_code=400,
            detail="All selected jobs are already queued or applied. Check Application status below.",
        )

    _enable_auto_apply(user.id)
    db.commit()
    for app in created:
        db.refresh(app)

    return ApplicationQueueResponse(
        queued=len(created),
        resumed=False,
        applications=[ApplicationResponse.model_validate(a) for a in created],
    )


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    apps = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
        .limit(100)
        .all()
    )
    return [ApplicationResponse.model_validate(a) for a in apps]


@router.get("/next", response_model=Optional[ApplicationResponse])
def next_queued_application(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    in_progress = (
        db.query(Application)
        .filter(Application.user_id == user.id, Application.status == "in_progress")
        .first()
    )
    if in_progress:
        return None

    app = (
        db.query(Application)
        .filter(Application.user_id == user.id, Application.status == "queued")
        .order_by(Application.created_at.asc())
        .first()
    )
    if not app:
        return None
    return ApplicationResponse.model_validate(app)


@router.get("/worker/next", response_model=Optional[ApplicationResponse])
def worker_next_application(
    _: None = Depends(verify_worker_secret),
    db: Session = Depends(get_db),
):
    if not _worker_apply_enabled:
        return None

    _release_stale_in_progress(db)

    in_progress = (
        db.query(Application).filter(Application.status == "in_progress").first()
    )
    if in_progress:
        return None

    query = db.query(Application).filter(Application.status == "queued")
    if _worker_apply_user_id is not None:
        query = query.filter(Application.user_id == _worker_apply_user_id)

    candidates = query.order_by(Application.created_at.asc()).limit(50).all()
    for candidate in candidates:
        if _is_lever_url(candidate.apply_url):
            return ApplicationResponse.model_validate(candidate)
    _maybe_disable_auto_apply(db)
    return None


@router.get("/worker/health")
def worker_health():
    return _worker_heartbeat


@router.post("/worker/heartbeat")
def worker_heartbeat(body: WorkerHeartbeatRequest, _: None = Depends(verify_worker_secret)):
    _worker_heartbeat["at"] = datetime.now(timezone.utc).isoformat()
    _worker_heartbeat["status"] = body.status
    _worker_heartbeat["message"] = body.message
    return {"ok": True}


@router.get("/{application_id}/payload", response_model=ApplyPayloadResponse)
def application_payload(
    app: Application = Depends(get_application_for_worker),
    db: Session = Depends(get_db),
):
    user = get_user_for_application(app, db)
    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=400, detail="User has no resume")

    answers_row = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()
    if not answers_row:
        raise HTTPException(status_code=400, detail="User has no application answers")

    resume_path, resume_filename = _stage_resume_for_worker(resume, app.id)
    parsed = None
    if resume.parsed_json:
        parsed = ParsedProfile.model_validate(resume.parsed_json)

    return ApplyPayloadResponse(
        application_id=app.id,
        user_id=user.id,
        access_token=create_access_token(str(user.id)),
        email=user.email,
        display_name=user.display_name,
        apply_url=app.apply_url,
        company=app.company,
        title=app.title,
        resume_path=resume_path,
        resume_filename=resume_filename,
        resume_mime=_resume_mime(resume.file_type),
        application_answers=ApplicationAnswersData.model_validate(answers_row, from_attributes=True),
        parsed_json=parsed,
    )


@router.post("/reset-stuck")
def reset_stuck_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stuck = (
        db.query(Application)
        .filter(
            Application.user_id == user.id,
            Application.status.in_(["in_progress", "blocked"]),
        )
        .all()
    )
    for app in stuck:
        app.status = "failed"
        app.message = "Reset — ready to re-queue"
    db.commit()
    return {"reset": len(stuck)}


@router.post("/{application_id}/report", response_model=ApplicationResponse)
def report_application(
    application_id: int,
    body: ApplicationReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.status not in REPORT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = body.status
    app.message = body.message or None
    db.commit()
    db.refresh(app)
    return ApplicationResponse.model_validate(app)


@router.post("/worker/{application_id}/report", response_model=ApplicationResponse)
def worker_report_application(
    application_id: int,
    body: ApplicationReportRequest,
    app: Application = Depends(get_application_for_worker),
    db: Session = Depends(get_db),
):
    if app.id != application_id:
        raise HTTPException(status_code=404, detail="Application not found")
    if body.status not in REPORT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    app.status = body.status
    app.message = body.message or None
    db.commit()
    db.refresh(app)
    if body.status in {"submitted", "failed", "blocked"}:
        _maybe_disable_auto_apply(db)
    return ApplicationResponse.model_validate(app)


def _answers_to_data(row: ApplicationAnswers | None) -> ApplicationAnswersData | None:
    if not row:
        return None
    return ApplicationAnswersData.model_validate(row, from_attributes=True)


@router.get("/answers", response_model=ApplicationAnswersResponse)
def get_application_answers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application answers not saved yet")
    return ApplicationAnswersResponse.model_validate(row)


@router.put("/answers", response_model=ApplicationAnswersResponse)
def update_application_answers(
    body: ApplicationAnswersData,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.city.strip():
        raise HTTPException(status_code=400, detail="City is required")
    if not body.phone.strip():
        raise HTTPException(status_code=400, detail="Phone is required")

    row = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()
    data = body.model_dump()
    if row:
        for key, val in data.items():
            setattr(row, key, val)
    else:
        row = ApplicationAnswers(user_id=user.id, **data)
        db.add(row)
    db.commit()
    db.refresh(row)
    return ApplicationAnswersResponse.model_validate(row)


@router.post("/answer-question", response_model=AnswerQuestionResponse)
def answer_custom_question(
    body: AnswerQuestionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _generate_answer(body, user, db)


@router.post("/worker/{application_id}/answer-question", response_model=AnswerQuestionResponse)
def worker_answer_custom_question(
    application_id: int,
    body: AnswerQuestionRequest,
    app: Application = Depends(get_application_for_worker),
    db: Session = Depends(get_db),
):
    if app.id != application_id:
        raise HTTPException(status_code=404, detail="Application not found")
    user = get_user_for_application(app, db)
    return _generate_answer(body, user, db)


def _generate_answer(body: AnswerQuestionRequest, user: User, db: Session) -> AnswerQuestionResponse:
    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    answers_row = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()
    profile = {"parsed_json": resume.parsed_json if resume else {}}
    answers = (
        ApplicationAnswersData.model_validate(answers_row, from_attributes=True).model_dump()
        if answers_row
        else ApplicationAnswersData().model_dump()
    )
    text = generate_text_answer(
        body.question,
        body.company,
        body.job_title,
        profile,
        answers,
    )
    return AnswerQuestionResponse(answer=text)


@router.get("/profile", response_model=ApplyProfileResponse)
def apply_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    parsed = None
    filename = None
    if resume:
        filename = resume.original_filename
        if resume.parsed_json:
            parsed = ParsedProfile.model_validate(resume.parsed_json)

    answers_row = db.query(ApplicationAnswers).filter(ApplicationAnswers.user_id == user.id).first()

    return ApplyProfileResponse(
        email=user.email,
        display_name=user.display_name,
        resume_filename=filename,
        parsed_json=parsed,
        application_answers=_answers_to_data(answers_row),
    )
