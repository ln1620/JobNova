from dataclasses import dataclass, field
from enum import Enum


class Stage(str, Enum):
    SELF_INTRO = "self_intro"
    PAST_EXPERIENCE = "past_experience"
    COMPLETE = "complete"


@dataclass
class InterviewUserData:
    email: str = ""
    user_id: int = 0
    interview_id: int = 0
    room_name: str = ""
    current_stage: Stage = Stage.SELF_INTRO
    handoff_in_progress: bool = False
    waiting_for_recorded_answer: bool = False
    self_intro_summary: str = ""
    experience_summary: str = ""
    transcript_parts: list[str] = field(default_factory=list)
    api_base: str = "http://localhost:8000"
