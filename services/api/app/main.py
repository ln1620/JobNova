from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

_root = Path(__file__).resolve().parents[3]
load_dotenv(_root / ".env")
load_dotenv(".env")

from app.config import get_settings
from app.database import init_db
from app.routers import (
    applications_router,
    auth_router,
    interview_router,
    jobs_router,
    preferences_router,
    resume_router,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobNova API", version="1.0.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(interview_router.router)
app.include_router(resume_router.router)
app.include_router(preferences_router.router)
app.include_router(jobs_router.router)
app.include_router(applications_router.router)
@app.get("/health")
def health():
    return {"status": "ok"}
