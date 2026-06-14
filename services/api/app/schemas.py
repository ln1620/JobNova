from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str]

    class Config:
        from_attributes = True


class InterviewStartResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str
    interview_id: int


class InterviewCompleteRequest(BaseModel):
    room_name: str
    self_intro_summary: str = ""
    experience_summary: str = ""
    transcript: str = ""


class InterviewResponse(BaseModel):
    id: int
    room_name: str
    status: str
    self_intro_summary: Optional[str]
    experience_summary: Optional[str]
    transcript: Optional[str]

    class Config:
        from_attributes = True


class EducationEntry(BaseModel):
    degree: str = ""
    school: str = ""
    year: str = ""


class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class ParsedProfile(BaseModel):
    skills: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    summary: str = ""
    years_experience: Optional[float] = None
    job_titles: list[str] = Field(default_factory=list)


class ResumeProfileUpdate(BaseModel):
    parsed_json: ParsedProfile


class ResumeProfileResponse(BaseModel):
    id: int
    original_filename: str
    file_type: str
    raw_text: Optional[str]
    parsed_json: Optional[ParsedProfile]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class ResumeUploadResponse(BaseModel):
    id: int
    original_filename: str
    file_type: str
    raw_text: Optional[str]
    parsed_json: Optional[ParsedProfile]
    message: str = "Resume processed successfully"
    parse_error: Optional[str] = None


class JobPreferenceData(BaseModel):
    job_titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_types: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None


class JobPreferenceUpdate(BaseModel):
    job_titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_types: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None


class JobPreferenceResponse(BaseModel):
    id: int
    job_titles: list[str]
    locations: list[str]
    work_types: list[str]
    seniority: Optional[str]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class SkillMatchDetailResponse(BaseModel):
    jd_skill: str
    resume_skill: Optional[str] = None
    match_score: float
    match_type: str
    importance: str
    weight: float


class MatchedJobResponse(BaseModel):
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
    matched_skills: list[str] = Field(default_factory=list)
    skill_match_details: list[SkillMatchDetailResponse] = Field(default_factory=list)


class JobDiscoverResponse(BaseModel):
    total_fetched: int
    total_analyzed: int
    total_matched: int
    min_skill_match: float = 0.60
    jobs: list[MatchedJobResponse]


class QueueJobItem(BaseModel):
    external_id: str
    company: str
    title: str
    location: str = ""
    apply_url: str


class ApplicationQueueRequest(BaseModel):
    consent: bool
    jobs: list[QueueJobItem]


class ApplicationReportRequest(BaseModel):
    status: str
    message: str = ""


class ApplicationResponse(BaseModel):
    id: int
    external_job_id: str
    company: str
    title: str
    location: str
    apply_url: str
    status: str
    message: Optional[str]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class ApplicationQueueResponse(BaseModel):
    queued: int
    resumed: bool = False
    applications: list[ApplicationResponse]


class ApplicationAnswersData(BaseModel):
    country: str = "United States"
    city: str = ""
    phone: str = ""
    linkedin_url: Optional[str] = None
    authorized_to_work: str = "Yes"
    require_sponsorship: str = "No"
    previously_employed: str = "No"
    veteran_status: str = "I am not a protected veteran"
    disability_status: str = "No, I do not have a disability"
    race: str = "Decline to self-identify"
    ethnicity: str = "Decline to self-identify"
    gender: str = "Decline to self-identify"

    class Config:
        from_attributes = True


class ApplicationAnswersResponse(ApplicationAnswersData):
    id: int
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class AnswerQuestionRequest(BaseModel):
    question: str
    company: str = ""
    job_title: str = ""


class AnswerQuestionResponse(BaseModel):
    answer: str


class ApplyProfileResponse(BaseModel):
    email: str
    display_name: Optional[str]
    resume_filename: Optional[str]
    parsed_json: Optional[ParsedProfile]
    application_answers: Optional[ApplicationAnswersData] = None


class ApplyPayloadResponse(BaseModel):
    application_id: int
    user_id: int
    access_token: str
    email: str
    display_name: Optional[str]
    apply_url: str
    company: str
    title: str
    resume_path: str
    resume_filename: str
    resume_mime: str
    application_answers: ApplicationAnswersData
    parsed_json: Optional[ParsedProfile] = None


class WorkerHeartbeatRequest(BaseModel):
    status: str = "running"
    message: str = ""
