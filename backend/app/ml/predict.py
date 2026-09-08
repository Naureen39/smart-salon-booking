"""Live no-show risk scoring, invoked synchronously at booking creation (docs
plan §10.3 — model inference itself is fast, <10ms; the DB lookups for
client/staff history dominate the actual latency here).
"""

import uuid
from datetime import datetime
from functools import lru_cache

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.appointment import Appointment
from app.ml.features import ALL_FEATURES, build_feature_row
from app.ml.train import GBM_MODEL_PATH

DEFAULT_RISK_SCORE = 0.12
"""The synthetic dataset's base rate — used when no trained model artifact
exists yet (a fresh dev/test environment before the first `python -m
app.ml.train` run), so booking creation never hard-fails on missing ML state.
"""


@lru_cache(maxsize=1)
def _load_model() -> Pipeline | None:
    if not GBM_MODEL_PATH.exists():
        return None
    return joblib.load(GBM_MODEL_PATH)


async def _client_history_stats(
    db: AsyncSession, client_id: uuid.UUID
) -> tuple[float, int, datetime | None]:
    total, no_shows, first_seen = (
        await db.execute(
            select(
                func.count(Appointment.id),
                func.sum(case((Appointment.status == "no_show", 1), else_=0)),
                func.min(Appointment.scheduled_start),
            ).where(Appointment.client_id == client_id, Appointment.status != "cancelled")
        )
    ).one()
    total = total or 0
    no_shows = no_shows or 0
    past_no_show_rate = (no_shows / total) if total else 0.0
    return past_no_show_rate, total, first_seen


async def _staff_no_show_rate(db: AsyncSession, staff_id: uuid.UUID) -> float:
    total, no_shows = (
        await db.execute(
            select(
                func.count(Appointment.id),
                func.sum(case((Appointment.status == "no_show", 1), else_=0)),
            ).where(Appointment.staff_id == staff_id, Appointment.status != "cancelled")
        )
    ).one()
    total = total or 0
    no_shows = no_shows or 0
    return (no_shows / total) if total else DEFAULT_RISK_SCORE


async def score_appointment(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    staff_id: uuid.UUID,
    scheduled_start: datetime,
    is_first_visit: bool,
    lead_time_hours: float,
    service_category: str | None,
    service_duration_minutes: int,
    service_price_cents: int,
    booking_channel: str | None,
) -> float:
    model = _load_model()
    if model is None:
        return DEFAULT_RISK_SCORE

    past_no_show_rate, total_visits, first_seen = await _client_history_stats(db, client_id)
    tenure_days = (scheduled_start - first_seen).days if first_seen else 0
    staff_rate = await _staff_no_show_rate(db, staff_id)

    row = build_feature_row(
        scheduled_start=scheduled_start,
        lead_time_hours=lead_time_hours,
        is_first_visit=is_first_visit,
        client_past_no_show_rate=past_no_show_rate,
        client_total_visits=total_visits,
        client_tenure_days=tenure_days,
        service_category=service_category,
        service_duration_minutes=service_duration_minutes,
        service_price_cents=service_price_cents,
        booking_channel=booking_channel,
        staff_no_show_rate_historical=staff_rate,
    )
    frame = pd.DataFrame([row])[ALL_FEATURES]
    probability = model.predict_proba(frame)[0, 1]
    return float(probability)
