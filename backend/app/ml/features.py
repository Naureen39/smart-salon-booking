"""Feature schema shared by training (app/ml/train.py) and live scoring
(app/ml/predict.py) — per docs plan §10.2, both paths must build the exact
same columns the exact same way, so a persisted model always sees what it
was trained on.
"""
from datetime import datetime

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = [
    "lead_time_hours",
    "day_of_week",
    "hour_of_day",
    "is_monday_morning",
    "is_first_visit",
    "client_past_no_show_rate",
    "client_total_visits",
    "client_tenure_days",
    "service_duration_minutes",
    "service_price_cents",
    "staff_no_show_rate_historical",
]
CATEGORICAL_FEATURES = ["service_category", "booking_channel"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "no_show"


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )


def build_feature_row(
    *,
    scheduled_start: datetime,
    lead_time_hours: float,
    is_first_visit: bool,
    client_past_no_show_rate: float,
    client_total_visits: int,
    client_tenure_days: int,
    service_category: str | None,
    service_duration_minutes: int,
    service_price_cents: int,
    booking_channel: str | None,
    staff_no_show_rate_historical: float,
) -> dict:
    """Builds one row with exactly the ALL_FEATURES columns — used for a single
    live-scoring prediction. Training rows come pre-built with these same
    column names directly from scripts/generate_synthetic_data.py."""
    return {
        "lead_time_hours": lead_time_hours,
        "day_of_week": scheduled_start.weekday(),
        "hour_of_day": scheduled_start.hour,
        "is_monday_morning": int(scheduled_start.weekday() == 0 and scheduled_start.hour < 10),
        "is_first_visit": int(is_first_visit),
        "client_past_no_show_rate": client_past_no_show_rate,
        "client_total_visits": client_total_visits,
        "client_tenure_days": client_tenure_days,
        "service_duration_minutes": service_duration_minutes,
        "service_price_cents": service_price_cents,
        "staff_no_show_rate_historical": staff_no_show_rate_historical,
        "service_category": service_category or "unknown",
        "booking_channel": booking_channel or "web",
    }
