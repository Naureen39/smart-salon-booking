import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.ml.predict as predict_module
from app.ml.predict import DEFAULT_RISK_SCORE, score_appointment
from app.ml.train import train_and_persist_models
from scripts.generate_synthetic_data import generate


@pytest.fixture(autouse=True)
def _clear_model_cache() -> None:
    predict_module._load_model.cache_clear()
    yield
    predict_module._load_model.cache_clear()


async def test_score_appointment_falls_back_to_default_when_no_model(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(predict_module, "GBM_MODEL_PATH", tmp_path / "does_not_exist.joblib")

    score = await score_appointment(
        db_session,
        client_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        scheduled_start=datetime.now(UTC),
        is_first_visit=True,
        lead_time_hours=48.0,
        service_category="Hair",
        service_duration_minutes=30,
        service_price_cents=3000,
        booking_channel="web",
    )
    assert score == DEFAULT_RISK_SCORE


async def test_score_appointment_uses_trained_model_when_available(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    df = generate(rows=1200, seed=11)
    data_path = tmp_path / "data.csv"
    df.to_csv(data_path, index=False)

    gbm_path = tmp_path / "gbm.joblib"
    train_and_persist_models(data_path, min_auc=None, gbm_path=gbm_path, logreg_path=tmp_path / "logreg.joblib")

    monkeypatch.setattr(predict_module, "GBM_MODEL_PATH", gbm_path)
    predict_module._load_model.cache_clear()

    score = await score_appointment(
        db_session,
        client_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        scheduled_start=datetime.now(UTC),
        is_first_visit=True,
        lead_time_hours=10.0,
        service_category="Spa",
        service_duration_minutes=90,
        service_price_cents=9000,
        booking_channel="chat",
    )
    assert 0.0 <= score <= 1.0
