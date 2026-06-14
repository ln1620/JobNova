from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException
from groq import Groq

from app.config import get_settings

IMPORTANCE_WEIGHTS = {
    "required": 1.0,
    "preferred": 0.6,
    "nice_to_have": 0.3,
}

MATCH_PROMPT = """You are an expert resume-to-job-description matcher.

Given a candidate's resume skills and a job description, you must:
1. Extract technical/professional skills from the JD
2. Label each skill's importance based on JD language:
   - "required" (must have, required, mandatory) → weight 1.0
   - "preferred" (preferred, strongly desired, plus) → weight 0.6
   - "nice_to_have" (nice to have, bonus, a plus) → weight 0.3
   Default to "required" if clearly in a Requirements section, else "preferred"
3. Match each JD skill against the resume skills using:
   - "exact" (same skill) → match_score 1.0
   - "equivalent" (same purpose, different tool, e.g. PyTorch↔TensorFlow, React↔Vue) → match_score 0.75
   - "partial" (related/overlapping domain) → match_score 0.5
   - "missing" (not on resume) → match_score 0.0

Compute skill_match_score = sum(importance_weight * match_score) / sum(importance_weight)
Round skill_match_score to 2 decimals (0.0 to 1.0).

Return ONLY valid JSON:
{
  "requirements": [
    {"skill": "Python", "importance": "required", "weight": 1.0}
  ],
  "matches": [
    {
      "jd_skill": "PyTorch",
      "resume_skill": "TensorFlow",
      "match_score": 0.75,
      "match_type": "equivalent",
      "importance": "preferred",
      "weight": 0.6
    }
  ],
  "skill_match_score": 0.72
}

Rules:
- Extract 5-20 meaningful skills from the JD (not soft skills like "team player" unless critical)
- Every requirement must appear in matches (use null resume_skill if missing)
- Be generous with equivalent matches for tools in the same category
- If JD has no clear skills, infer from title and description

Resume skills:
{resume_skills}

Job title: {job_title}

Job description:
{jd_text}
"""


@dataclass
class SkillMatchDetail:
    jd_skill: str
    resume_skill: str | None
    match_score: float
    match_type: str
    importance: str
    weight: float


@dataclass
class JdSkillMatchResult:
    skill_match_score: float
    matches: list[SkillMatchDetail]
    requirements: list[dict]


def _compute_score_from_matches(matches: list[dict]) -> float:
    total_weight = 0.0
    earned = 0.0
    for m in matches:
        weight = float(m.get("weight") or IMPORTANCE_WEIGHTS.get(m.get("importance", "preferred"), 0.6))
        score = float(m.get("match_score") or 0.0)
        total_weight += weight
        earned += weight * score
    if total_weight <= 0:
        return 0.0
    return round(min(earned / total_weight, 1.0), 3)


def _parse_llm_result(data: dict) -> JdSkillMatchResult:
    matches_raw = data.get("matches") or []
    requirements = data.get("requirements") or []

    matches: list[SkillMatchDetail] = []
    for m in matches_raw:
        importance = str(m.get("importance") or "preferred").lower()
        if importance not in IMPORTANCE_WEIGHTS:
            importance = "preferred"
        weight = float(m.get("weight") or IMPORTANCE_WEIGHTS[importance])
        matches.append(
            SkillMatchDetail(
                jd_skill=str(m.get("jd_skill") or ""),
                resume_skill=m.get("resume_skill"),
                match_score=min(max(float(m.get("match_score") or 0.0), 0.0), 1.0),
                match_type=str(m.get("match_type") or "missing"),
                importance=importance,
                weight=weight,
            )
        )

    llm_score = data.get("skill_match_score")
    if llm_score is not None:
        skill_match_score = min(max(float(llm_score), 0.0), 1.0)
    else:
        skill_match_score = _compute_score_from_matches(matches_raw)

    return JdSkillMatchResult(
        skill_match_score=round(skill_match_score, 3),
        matches=matches,
        requirements=requirements,
    )


def match_resume_to_jd(
    resume_skills: list[str],
    job_title: str,
    jd_text: str,
) -> JdSkillMatchResult | None:
    settings = get_settings()
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured")

    if not jd_text.strip() or not resume_skills:
        return None

    skills_block = "\n".join(f"- {s}" for s in resume_skills if s.strip())
    # Use replace — not .format() — the prompt contains JSON with curly braces
    prompt = (
        MATCH_PROMPT.replace("{resume_skills}", skills_block)
        .replace("{job_title}", job_title)
        .replace("{jd_text}", jd_text[:8000])
    )

    client = Groq(api_key=settings.groq_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": "You match resumes to job descriptions. Respond with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    except Exception:
        return None

    content = response.choices[0].message.content
    if not content:
        return None

    try:
        data = json.loads(content)
        return _parse_llm_result(data)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
