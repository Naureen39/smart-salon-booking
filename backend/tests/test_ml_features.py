from datetime import UTC, datetime

from app.ml.features import ALL_FEATURES, build_feature_row, build_preprocessor


def test_build_feature_row_is_deterministic() -> None:
    scheduled_start = datetime(2026, 9, 14, 9, 30, tzinfo=UTC)  # a Monday

    kwargs = {
        "scheduled_start": scheduled_start,
        "lead_time_hours": 48.0,
        "is_first_visit": True,
        "client_past_no_show_rate": 0.0,
        "client_total_visits": 0,
        "client_tenure_days": 0,
        "service_category": "Hair",
        "service_duration_minutes": 30,
        "service_price_cents": 3000,
        "booking_channel": "web",
        "staff_no_show_rate_historical": 0.1,
    }

    row1 = build_feature_row(**kwargs)
    row2 = build_feature_row(**kwargs)

    assert row1 == row2
    assert set(row1.keys()) == set(ALL_FEATURES)
    assert row1["day_of_week"] == 0
    assert row1["is_monday_morning"] == 1


def test_build_feature_row_flags_non_monday_morning_correctly() -> None:
    tuesday_afternoon = datetime(2026, 9, 15, 14, 0, tzinfo=UTC)
    row = build_feature_row(
        scheduled_start=tuesday_afternoon,
        lead_time_hours=10.0,
        is_first_visit=False,
        client_past_no_show_rate=0.2,
        client_total_visits=3,
        client_tenure_days=90,
        service_category=None,
        service_duration_minutes=60,
        service_price_cents=6000,
        booking_channel=None,
        staff_no_show_rate_historical=0.12,
    )
    assert row["is_monday_morning"] == 0
    assert row["service_category"] == "unknown"
    assert row["booking_channel"] == "web"


def test_build_preprocessor_is_freshly_constructed_each_call() -> None:
    a = build_preprocessor()
    b = build_preprocessor()
    assert a is not b
