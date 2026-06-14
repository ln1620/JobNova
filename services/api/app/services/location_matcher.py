from __future__ import annotations

import re

# User input → canonical country key
COUNTRY_ALIASES: dict[str, str] = {
    "usa": "usa",
    "us": "usa",
    "u.s.": "usa",
    "u.s.a.": "usa",
    "united states": "usa",
    "united states of america": "usa",
    "america": "usa",
    "canada": "canada",
    "ca": "canada",
    "uk": "uk",
    "united kingdom": "uk",
    "england": "uk",
    "india": "india",
    "germany": "germany",
    "france": "france",
    "australia": "australia",
    "ireland": "ireland",
    "singapore": "singapore",
    "netherlands": "netherlands",
    "spain": "spain",
    "sweden": "sweden",
    "japan": "japan",
    "mexico": "mexico",
    "brazil": "brazil",
}

# Patterns that indicate a job is in the USA
USA_PATTERNS: list[str] = [
    r"\busa\b",
    r"\bu\.s\.?\b",
    r"\bus\b",
    r"united states",
    r"\busa?-remote\b",
    r"\bus-remote\b",
    r"remote[\s-]*us\b",
    r"remote in (the )?us\b",
    r"remote in (the )?united states\b",
    r"remote[\s-]*united states\b",
    r"north america",
]

US_STATE_CODES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in",
    "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
    "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
    "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}

US_CITIES = {
    "new york", "nyc", "san francisco", "seattle", "chicago", "boston", "austin",
    "los angeles", "denver", "atlanta", "miami", "dallas", "houston", "phoenix",
    "portland", "san diego", "san jose", "philadelphia", "washington",
}

COUNTRY_MARKERS: dict[str, list[str]] = {
    "usa": USA_PATTERNS,
    "canada": [r"\bcanada\b", r"\bcan\b", r"can-remote", r"remote[\s-]*canada", r"toronto", r"vancouver", r"montreal"],
    "uk": [r"\buk\b", r"united kingdom", r"\bengland\b", r"\blondon\b"],
    "india": [r"\bindia\b", r"\bbangalore\b", r"\bmumbai\b", r"\bdelhi\b", r"\bhyderabad\b"],
    "germany": [r"\bgermany\b", r"\bberlin\b", r"\bmunich\b"],
    "france": [r"\bfrance\b", r"\bparis\b"],
    "australia": [r"\baustralia\b", r"\bsydney\b", r"\bmelbourne\b"],
    "ireland": [r"\bireland\b", r"\bdublin\b"],
    "singapore": [r"\bsingapore\b"],
    "netherlands": [r"\bnetherlands\b", r"\bamsterdam\b"],
    "spain": [r"\bspain\b", r"\bmadrid\b", r"\bbarcelona\b"],
    "sweden": [r"\bsweden\b", r"\bstockholm\b"],
    "japan": [r"\bjapan\b", r"\btokyo\b"],
    "mexico": [r"\bmexico\b"],
    "brazil": [r"\bbrazil\b", r"\bsão paulo\b", r"\bsao paulo\b"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def canonical_countries(user_locations: list[str]) -> list[str]:
    countries: list[str] = []
    for loc in user_locations:
        key = _normalize(loc)
        if not key:
            continue
        canonical = COUNTRY_ALIASES.get(key, key)
        if canonical not in countries:
            countries.append(canonical)
    return countries


def _matches_patterns(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.I):
            return True
    return False


def _has_us_state_or_city(text: str) -> bool:
    if re.search(r",\s*([a-z]{2})\b", text):
        code = re.search(r",\s*([a-z]{2})\b", text).group(1).lower()
        if code in US_STATE_CODES:
            return True
    for city in US_CITIES:
        if city in text:
            return True
    return False


def _detect_countries_in_job_location(job_location: str) -> set[str]:
    text = _normalize(job_location)
    found: set[str] = set()

    for country, patterns in COUNTRY_MARKERS.items():
        if _matches_patterns(text, patterns):
            found.add(country)

    if _has_us_state_or_city(text) and "canada" not in text:
        found.add("usa")

    remote_country = re.search(r"remote\s*[-–—]\s*([a-z\s]+)", text, re.I)
    if remote_country:
        segment = remote_country.group(1).strip()
        for alias, canonical in COUNTRY_ALIASES.items():
            if alias in segment or segment == canonical:
                found.add(canonical)
        for country, patterns in COUNTRY_MARKERS.items():
            if _matches_patterns(segment, patterns):
                found.add(country)

    return found


def job_matches_user_countries(job_location: str, user_locations: list[str]) -> bool:
    """Strict filter: job must be in at least one of the user's target countries."""
    if not user_locations:
        return True

    user_countries = canonical_countries(user_locations)
    if not user_countries:
        return True

    job_countries = _detect_countries_in_job_location(job_location)
    if not job_countries:
        return False

    return bool(job_countries & set(user_countries))


def location_match_score(job_location: str, user_locations: list[str]) -> float:
    """1.0 only when the job is in the user's country, else 0.0."""
    return 1.0 if job_matches_user_countries(job_location, user_locations) else 0.0
