from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Resume, User
from app.routers.auth_router import get_current_user
from app.schemas import (
    ParsedProfile,
    ResumeProfileResponse,
    ResumeProfileUpdate,
    ResumeUploadResponse,
)
from app.services.ocr_parser import detect_file_type, extract_text
from app.services.resume_parser import extract_profile_from_text

router = APIRouter(prefix="/resume", tags=["resume"])

UPLOAD_ROOT = Path(__file__).resolve().parents[4] / "uploads" / "resumes"


def _resume_to_response(resume: Resume) -> ResumeProfileResponse:
    parsed = None
    if resume.parsed_json:
        parsed = ParsedProfile.model_validate(resume.parsed_json)
    return ResumeProfileResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        file_type=resume.file_type,
        raw_text=resume.raw_text,
        parsed_json=parsed,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


def _get_user_resume(db: Session, user_id: int) -> Resume | None:
    return db.query(Resume).filter(Resume.user_id == user_id).first()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_type = detect_file_type(file.filename)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    raw_text = extract_text(file_bytes, file_type)

    parsed_json = None
    parse_error: str | None = None
    try:
        parsed_json = extract_profile_from_text(raw_text)
    except HTTPException as exc:
        parse_error = str(exc.detail)

    user_dir = UPLOAD_ROOT / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name
    dest_path = user_dir / safe_name
    dest_path.write_bytes(file_bytes)

    existing = _get_user_resume(db, user.id)
    if existing:
        if existing.file_path != str(dest_path) and Path(existing.file_path).exists():
            Path(existing.file_path).unlink(missing_ok=True)
        existing.file_path = str(dest_path)
        existing.original_filename = safe_name
        existing.file_type = file_type
        existing.raw_text = raw_text
        existing.parsed_json = parsed_json
        resume = existing
    else:
        resume = Resume(
            user_id=user.id,
            file_path=str(dest_path),
            original_filename=safe_name,
            file_type=file_type,
            raw_text=raw_text,
            parsed_json=parsed_json,
        )
        db.add(resume)

    db.commit()
    db.refresh(resume)

    response = _resume_to_response(resume)
    message = "Resume processed successfully"
    if parse_error:
        message = (
            f"Text extracted but skill parsing failed: {parse_error}. "
            "You can edit your profile manually below."
        )
    return ResumeUploadResponse(
        id=response.id,
        original_filename=response.original_filename,
        file_type=response.file_type,
        raw_text=response.raw_text,
        parsed_json=response.parsed_json,
        message=message,
        parse_error=parse_error,
    )


@router.get("/profile", response_model=ResumeProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_user_resume(db, user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume uploaded yet")
    return _resume_to_response(resume)


@router.put("/profile", response_model=ResumeProfileResponse)
def update_profile(
    body: ResumeProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_user_resume(db, user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume uploaded yet")

    resume.parsed_json = body.parsed_json.model_dump()
    db.commit()
    db.refresh(resume)
    return _resume_to_response(resume)


@router.get("/download")
def download_resume(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_user_resume(db, user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="No resume uploaded yet")
    path = Path(resume.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    media = "application/pdf" if resume.file_type == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(path, filename=resume.original_filename, media_type=media)
