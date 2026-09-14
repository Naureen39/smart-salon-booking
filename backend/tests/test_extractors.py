from datetime import date, datetime

from app.ai.extractors import extract_date

REFERENCE = datetime(2026, 9, 10)  # a Thursday


def test_day_then_month_with_no_year_uses_the_reference_year() -> None:
    """Regression test for a real bug found in manual end-to-end testing: a
    date like "11th Sep" has no year, and dateparser's STRICT_PARSING (needed
    to avoid misreading unrelated words like "to" as a date) requires a
    complete day+month+year expression, so it returned nothing for this. That
    sent the message to the LLM extractor instead, which has no notion of
    "today" and invented an arbitrary year (2023) for the ISO date it
    returned, three years in the past.
    """
    assert extract_date("11th Sep", reference_date=REFERENCE) == date(2026, 9, 11)


def test_month_then_day_with_no_year_uses_the_reference_year() -> None:
    assert extract_date("Sep 11", reference_date=REFERENCE) == date(2026, 9, 11)
    assert extract_date("September 11th", reference_date=REFERENCE) == date(2026, 9, 11)


def test_day_month_already_passed_this_year_rolls_over_to_next_year() -> None:
    assert extract_date("Jan 5", reference_date=REFERENCE) == date(2027, 1, 5)


def test_explicit_year_is_still_respected_over_the_reference_year() -> None:
    assert extract_date("11th Sep 2030", reference_date=REFERENCE) == date(2030, 9, 11)


def test_unparseable_text_still_returns_none() -> None:
    assert extract_date("I want to book a Haircut", reference_date=REFERENCE) is None
