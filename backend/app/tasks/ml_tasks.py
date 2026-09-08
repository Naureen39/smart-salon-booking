"""Celery task for the weekly no-show model retraining job (docs plan §10.3).
Runs on synthetic data today; swapping to real accumulated booking history
later means changing what train_and_persist_models reads, not this task.
"""

from pathlib import Path

from app.ml.train import train_and_persist_models
from app.tasks.celery_app import celery_app

DEFAULT_TRAINING_DATA_PATH = Path("data/synthetic_appointments.csv")


@celery_app.task(name="ml.retrain_no_show_model")
def retrain_no_show_model() -> dict:
    return train_and_persist_models(DEFAULT_TRAINING_DATA_PATH)
