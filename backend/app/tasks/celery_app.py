from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "glowdesk",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ml_tasks", "app.tasks.reminders"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
celery_app.conf.beat_schedule = {
    "retrain-no-show-model-weekly": {
        "task": "ml.retrain_no_show_model",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
}
