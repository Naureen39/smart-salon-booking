"""Rule-based first-pass parsers for the conversation orchestrator (docs plan
§9.1) — date/time and service-name extraction that runs before ever
considering an LLM call. Keeping this deterministic and dependency-light is
what makes most turns cost zero tokens.
"""

import re
from datetime import date, datetime, timedelta

from dateparser.search import search_dates
from rapidfuzz import fuzz, process

# STRICT_PARSING is essential here: dateparser's default (loose) search_dates
# treats short, unrelated words as date fragments — e.g. on "I want to book a
# Haircut" it matched "to" as a date. Strict mode requires a genuinely
# complete date expression (day+month+year, or an unambiguous relative term
# like "tomorrow"), which eliminates that false-positive class. Its cost is
# missing bare weekday references ("next Monday"), so those are handled
# separately by _extract_weekday below, before dateparser ever runs.
_DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
    "STRICT_PARSING": True,
}

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAY_PATTERN = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE)

TIME_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (5, 12),
    "afternoon": (12, 17),
    "evening": (17, 22),
}

SERVICE_MATCH_THRESHOLD = 70


def _extract_weekday(text: str, reference_date: date) -> date | None:
    match = _WEEKDAY_PATTERN.search(text)
    if match is None:
        return None
    target_weekday = _WEEKDAYS.index(match.group(1).lower())
    days_ahead = (target_weekday - reference_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # naming today's weekday means the *next* occurrence, not today
    return reference_date + timedelta(days=days_ahead)


def extract_date(text: str, *, reference_date: datetime | None = None) -> date | None:
    base = (reference_date or datetime.now()).date()

    weekday_match = _extract_weekday(text, base)
    if weekday_match is not None:
        return weekday_match

    settings = dict(_DATEPARSER_SETTINGS)
    if reference_date is not None:
        settings["RELATIVE_BASE"] = reference_date
    results = search_dates(text, settings=settings)
    if not results:
        return None
    return results[0][1].date()


def extract_time_window(text: str) -> str | None:
    lowered = text.lower()
    if "morning" in lowered:
        return "morning"
    if "afternoon" in lowered:
        return "afternoon"
    if "evening" in lowered or "night" in lowered:
        return "evening"
    return None


def match_service(text: str, service_names: list[str], *, threshold: int = SERVICE_MATCH_THRESHOLD) -> str | None:
    if not service_names:
        return None
    match = process.extractOne(text, service_names, scorer=fuzz.partial_ratio)
    if match is None:
        return None
    name, score, _ = match
    return name if score >= threshold else None
