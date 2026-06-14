from __future__ import annotations

import json

from fastapi import HTTPException
from groq import Groq

from app.config import get_settings

# Map question label keywords → application_answers field
DROPDOWN_RULES: list[tuple[list[str], str]] = [
    (["authorized to work", "legally authorized", "eligible to work"], "authorized_to_work"),
    (["require sponsorship", "visa sponsorship", "immigration sponsorship"], "require_sponsorship"),
    (["worked for", "employed by", "contractor", "consultant", "worked at"], "previously_employed"),
    (["veteran"], "veteran_status"),
    (["disability"], "disability_status"),
    (["race"], "race"),
    (["ethnicity", "ethnic"], "ethnicity"),
    (["gender"], "gender"),
]


def match_dropdown_answer(label: str, answers: dict) -> str | None:
    lower = label.lower()
    for keywords, field in DROPDOWN_RULES:
        if any(k in lower for k in keywords):
            val = answers.get(field)
            if val:
                return val
    if "yes" in lower or "no" in lower:
        if "sponsor" in lower:
            return answers.get("require_sponsorship") or "No"
        if "authorized" in lower or "eligible" in lower:
            return answers.get("authorized_to_work") or "Yes"
        if "worked" in lower or "employed" in lower or "before" in lower:
            return answers.get("previously_employed") or "No"
    return None


def generate_text_answer(
    question: str,
    company: str,
    job_title: str,
    profile: dict,
    answers: dict,
) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        summary = (profile.get("parsed_json") or {}).get("summary") or ""
        skill_list = (profile.get("parsed_json") or {}).get("skills") or []
        skills = ", ".join(skill_list[:8])
        return (
            f"I am excited about the {job_title} role at {company}. "
            f"My background in {skills or 'software engineering'} aligns well with this opportunity. "
            f"{summary[:200]}"
        ).strip()

    skills = (profile.get("parsed_json") or {}).get("skills") or []
    summary = (profile.get("parsed_json") or {}).get("summary") or ""
    city = answers.get("city") or ""

    prompt = f"""Write a concise, professional job application answer (2-4 sentences, under 80 words).
Be specific to the company and role. Sound human, not generic.

Company: {company}
Role: {job_title}
Candidate city: {city}
Skills: {", ".join(skills[:10])}
Summary: {summary[:400]}

Question: {question}

Answer:"""

    client = Groq(api_key=settings.groq_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You write short job application answers. Plain text only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        text = (response.choices[0].message.content or "").strip()
        return text if text else "I am very interested in this role and believe my experience is a strong fit."
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not generate answer: {exc}") from exc
