"""Reminder scheduling per docs plan §10.4 — cadence and message urgency scale
with the no-show risk score computed at booking time. Each reminder is its own
individually-scheduled Celery task (via `apply_async(eta=...)`) rather than a
periodic sweep, so timing is exact per appointment.

Cancellation/reschedule handling: rather than tracking and revoking Celery task
IDs, each reminder re-checks the appointment's current status and scheduled
time right before sending. A cancelled appointment's pending reminders become
silent no-ops; a rescheduled appointment gets a fresh batch queued (see
schedule_reminders' call sites in app/api/v1/appointments.py) while its old,
now-stale reminders self-skip on the scheduled_start mismatch. This is simpler
and more robust than task-ID tracking (survives worker restarts, needs no
extra DB column) at the cost of a few harmless no-op task executions.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models.appointment import Appointment
from app.db.models.service import Service
from app.db.models.user import User
from app.notifications.email_channel import EmailChannel
from app.tasks.celery_app import celery_app

settings = get_settings()

REMINDER_OFFSETS_HOURS: dict[str, list[float]] = {
    "low": [24],
    "medium": [48, 4],
    "high": [72, 24, 2],
}

ACTIVE_STATUSES = ("booked", "confirmed")


def get_risk_tier(score: float) -> str:
    if score < 0.3:
        return "low"
    if score <= 0.6:
        return "medium"
    return "high"


def schedule_reminders(appointment: Appointment) -> None:
    """Queues one Celery task per reminder offset for this appointment's risk
    tier. Call this after committing a booking creation or reschedule."""
    tier = get_risk_tier(appointment.no_show_risk_score or 0.0)
    now = datetime.now(UTC)

    for offset_hours in REMINDER_OFFSETS_HOURS[tier]:
        reminder_time = appointment.scheduled_start - timedelta(hours=offset_hours)
        if reminder_time <= now:
            continue  # this offset has already passed — e.g. a short-lead-time booking

        send_appointment_reminder.apply_async(
            args=[
                str(appointment.id),
                offset_hours,
                tier,
                appointment.scheduled_start.isoformat(),
            ],
            eta=reminder_time,
        )


def _build_message(client: User, service: Service, appointment: Appointment, tier: str) -> tuple[str, str]:
    when = appointment.scheduled_start.strftime("%A, %B %d at %I:%M %p %Z")
    subject = f"Reminder: your {service.name} appointment is coming up"
    body = f"Hi {client.full_name},\n\nThis is a reminder that you have a {service.name} appointment on {when}.\n"

    if tier == "high":
        body += (
            "\nPlease reply YES to confirm, or let us know if you need to reschedule — "
            "otherwise we may need to release your slot to another client.\n"
        )

    body += "\nWe look forward to seeing you!\nGlowDesk"
    return subject, body


async def _send_reminder(
    appointment_id: str, tier: str, expected_scheduled_start_iso: str
) -> str:
    # A fresh engine per task invocation, not the app's module-level singleton:
    # Celery's sync task model means each call gets its own asyncio.run() event
    # loop, and asyncpg connections are loop-bound — reusing a pooled engine
    # across separate loops raises "attached to a different loop" errors.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as db:
            appointment = await db.get(Appointment, uuid.UUID(appointment_id))
            if appointment is None:
                return "skipped: appointment not found"
            if appointment.status not in ACTIVE_STATUSES:
                return f"skipped: status={appointment.status}"
            if appointment.scheduled_start.isoformat() != expected_scheduled_start_iso:
                return "skipped: rescheduled since this reminder was queued"

            client = await db.get(User, appointment.client_id)
            service = await db.get(Service, appointment.service_id)
            if client is None or service is None:
                return "skipped: missing client or service"

            subject, body = _build_message(client, service, appointment, tier)
            EmailChannel().send(to=client.email, subject=subject, body=body)

            reminder_log = list(appointment.reminder_sent_at or [])
            reminder_log.append(datetime.now(UTC))
            appointment.reminder_sent_at = reminder_log
            await db.commit()
            return "sent"
    finally:
        await engine.dispose()


@celery_app.task(name="reminders.send_appointment_reminder")
def send_appointment_reminder(
    appointment_id: str, offset_hours: float, tier: str, expected_scheduled_start_iso: str
) -> str:
    del offset_hours  # not needed at send time, kept for task-arg readability/debugging
    return asyncio.run(_send_reminder(appointment_id, tier, expected_scheduled_start_iso))
