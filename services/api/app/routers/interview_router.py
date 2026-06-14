import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from livekit import api
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Interview, User
from app.routers.auth_router import get_current_user
from app.schemas import (
    InterviewCompleteRequest,
    InterviewResponse,
    InterviewStartResponse,
)

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/start", response_model=InterviewStartResponse)
async def start_interview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="LiveKit credentials missing in .env")

    room_name = f"interview-{user.id}-{uuid.uuid4().hex[:8]}"
    interview = Interview(user_id=user.id, room_name=room_name, status="in_progress")
    db.add(interview)
    db.commit()
    db.refresh(interview)

    metadata = json.dumps({"email": user.email, "user_id": user.id, "interview_id": interview.id})
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(user.email)
        .with_name(user.display_name or user.email)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .with_metadata(metadata)
    )

    # Dispatch voice agent to this room (must match agent_name in agents/interview/main.py)
    try:
        lk = api.LiveKitAPI(
            settings.livekit_url.replace("wss://", "https://").replace("ws://", "http://"),
            settings.livekit_api_key,
            settings.livekit_api_secret,
        )
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="jobnova-interview",
                room=room_name,
                metadata=metadata,
            )
        )
        await lk.aclose()
    except Exception as e:
        import logging

        logging.getLogger("jobnova").warning("Agent dispatch failed: %s", e)

    return InterviewStartResponse(
        room_name=room_name,
        token=token.to_jwt(),
        livekit_url=settings.livekit_url,
        interview_id=interview.id,
    )


@router.post("/complete", response_model=InterviewResponse)
def complete_interview(
    body: InterviewCompleteRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.room_name == body.room_name).first()
    if not interview:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Interview not found")

    interview.status = "completed"
    interview.self_intro_summary = body.self_intro_summary
    interview.experience_summary = body.experience_summary
    interview.transcript = body.transcript
    interview.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == user.id)
        .first()
    )
    if not interview:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


@router.get("/history/list", response_model=list[InterviewResponse])
def list_interviews(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Interview)
        .filter(Interview.user_id == user.id)
        .order_by(Interview.created_at.desc())
        .limit(10)
        .all()
    )
    return rows
