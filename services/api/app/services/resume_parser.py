from __future__ import annotations

import json

from fastapi import HTTPException
from groq import Groq

from app.config import get_settings
from app.schemas import ParsedProfile

EXTRACTION_PROMPT = """You are a resume parser. Extract structured information from the resume text below.

Return ONLY valid JSON with this exact shape:
{
  "skills": ["skill1", "skill2"],
  "education": [{"degree": "", "school": "", "year": ""}],
  "experience": [{"title": "", "company": "", "start": "", "end": "", "bullets": ["..."]}],
  "summary": "brief professional summary",
  "years_experience": 0,
  "job_titles": ["most recent or relevant titles"]
}

Rules:
- skills: technical and professional skills only, deduplicated
- education: all degrees/certifications found
- experience: work history in reverse chronological order; bullets are key achievements/responsibilities
- years_experience: estimated total years as a number (use null if unclear)
- job_titles: titles held or targeted from the resume
- Use empty strings or empty arrays when information is missing
- Do not invent information not present in the text

Resume text:
"""


def extract_profile_from_text(raw_text: str) -> dict:
    settings = get_settings()
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured. Add it to your .env file.",
        )

    client = Groq(api_key=settings.groq_api_key)
    truncated = raw_text[:12000]

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured resume data. Respond with JSON only.",
                },
                {"role": "user", "content": EXTRACTION_PROMPT + truncated},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Groq extraction failed: {exc}",
        ) from exc

    content = response.choices[0].message.content
    if not content:
        raise HTTPException(status_code=502, detail="Groq returned an empty response")

    try:
        data = json.loads(content)
        profile = ParsedProfile.model_validate(data)
        return profile.model_dump()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not parse Groq response as profile JSON: {exc}",
        ) from exc
