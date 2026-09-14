"""Rule-based first-pass parsers for the conversation orchestrator (docs plan
§9.1), date/time and service-name extraction that runs before ever
considering an LLM call. Keeping this deterministic and dependency-light is
what makes most turns cost zero tokens.
"""

import re
from datetime import date, datetime, time, timedelta

from dateparser.search import search_dates
from rapidfuzz import fuzz, process

# STRICT_PARSING is essential here: dateparser's default (loose) search_dates
# treats short, unrelated words as date fragments, e.g. on "I want to book a
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

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_MONTH_NAMES_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
# day-then-month ("11th Sep") or month-then-day ("Sep 11"), with no year.
_DAY_MONTH_PATTERN = re.compile(
    rf"\b(?:(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{_MONTH_NAMES_PATTERN})\b"
    rf"|(?P<month2>{_MONTH_NAMES_PATTERN})\s+(?P<day2>\d{{1,2}})(?:st|nd|rd|th)?\b)",
    re.IGNORECASE,
)


def _extract_day_month(text: str, reference_date: date) -> date | None:
    """Fallback for "11th Sep" / "Sep 11" style dates with no year. STRICT_PARSING
    (see the comment above `_DATEPARSER_SETTINGS`) requires a complete
    day+month+year expression, so dateparser itself returns nothing for these
    even though they're an extremely common way to say a date; without this,
    that ambiguous case fell through to the LLM extractor, which has no
    notion of "today" and would guess an arbitrary (sometimes past) year for
    the ISO date it emits. Found in manual end-to-end testing: "11th Sep" was
    booked against 2023-09-11, three years in the past, because the LLM
    invented that year out of thin air.
    """
    match = _DAY_MONTH_PATTERN.search(text)
    if match is None:
        return None
    month = _MONTHS[(match.group("month") or match.group("month2")).lower()]
    day = int(match.group("day") or match.group("day2"))
    try:
        candidate = date(reference_date.year, month, day)
    except ValueError:
        return None
    if candidate < reference_date:
        candidate = date(reference_date.year + 1, month, day)
    return candidate


TIME_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (5, 12),
    "afternoon": (12, 17),
    "evening": (17, 22),
}

SERVICE_MATCH_THRESHOLD = 70

_TIME_12H_RE = re.compile(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*([ap])\.?m\.?\b", re.IGNORECASE)
_TIME_24H_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


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
    if results:
        return results[0][1].date()

    return _extract_day_month(text, base)


def extract_time_window(text: str) -> str | None:
    lowered = text.lower()
    if "morning" in lowered:
        return "morning"
    if "afternoon" in lowered:
        return "afternoon"
    if "evening" in lowered or "night" in lowered:
        return "evening"
    return None


def extract_specific_time(text: str) -> time | None:
    """Parses an explicit clock time like "3pm", "3:30 pm", or "15:00" out of
    free text. This is deliberately separate from `extract_time_window` (which
    only recognizes broad "morning"/"afternoon"/"evening" phrasing). A request
    like "book a haircut at 3pm" names an exact time, and slot presentation
    should prioritize options closest to it rather than just the day's
    earliest openings.
    """
    match = _TIME_12H_RE.search(text)
    if match:
        hour = int(match.group(1)) % 12
        minute = int(match.group(2) or 0)
        if match.group(3).lower() == "p":
            hour += 12
        return time(hour, minute)
    match = _TIME_24H_RE.search(text)
    if match:
        return time(int(match.group(1)), int(match.group(2)))
    return None


def match_service(text: str, service_names: list[str], *, threshold: int = SERVICE_MATCH_THRESHOLD) -> str | None:
    if not service_names:
        return None
    match = process.extractOne(text, service_names, scorer=fuzz.partial_ratio)
    if match is None:
        return None
    name, score, _ = match
    return name if score >= threshold else None
