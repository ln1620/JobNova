from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Application, User


def verify_worker_secret(
    x_worker_secret: Optional[str] = Header(default=None, alias="X-Worker-Secret"),
) -> None:
    settings = get_settings()
    if not settings.apply_worker_secret:
        raise HTTPException(status_code=503, detail="Apply worker not configured")
    if not x_worker_secret or x_worker_secret != settings.apply_worker_secret:
        raise HTTPException(status_code=401, detail="Invalid worker secret")


def get_application_for_worker(
    application_id: int,
    _: None = Depends(verify_worker_secret),
    db: Session = Depends(get_db),
) -> Application:
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def get_user_for_application(app: Application, db: Session) -> User:
    user = db.query(User).filter(User.id == app.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
