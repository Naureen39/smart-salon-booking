"""Shared appointment-creation logic, used by both the REST endpoint
(app/api/v1/appointments.py) and the conversation orchestrator (app/ai/
orchestrator.py) — risk scoring, audit logging, and reminder scheduling must
happen identically regardless of which channel booked the appointment.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.db.models.appointment import Appointment
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.ml.predict import score_appointment
from app.tasks.reminders import schedule_reminders


class ServiceNotFoundError(Exception):
    pass


class StaffNotFoundError(Exception):
    pass


class BookingConflictError(Exception):
    """Raised when the requested slot is no longer available at insert time."""


async def create_booking(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    scheduled_start: datetime,
    booking_channel: str,
) -> Appointment:
    service = await db.get(Service, service_id)
    if service is None:
        raise ServiceNotFoundError(f"Service {service_id} not found")

    staff = await db.get(StaffProfile, staff_id)
    if staff is None:
        raise StaffNotFoundError(f"Staff profile {staff_id} not found")
    # Derived from the staff member's own profile rather than accepted as a
    # caller-supplied value — a client passing a location_id that doesn't
    # match the chosen staff member's actual location would otherwise create
    # an appointment record inconsistent with itself, silently corrupting any
    # per-location reporting.
    location_id = staff.location_id

    scheduled_end = scheduled_start + timedelta(minutes=service.duration_minutes)

    prior_count = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.client_id == client_id, Appointment.status != "cancelled")
    )
    is_first_visit = prior_count == 0
    lead_time_hours = (scheduled_start - datetime.now(UTC)).total_seconds() / 3600

    no_show_risk_score = await score_appointment(
        db,
        client_id=client_id,
        staff_id=staff_id,
        scheduled_start=scheduled_start,
        is_first_visit=is_first_visit,
        lead_time_hours=lead_time_hours,
        service_category=service.category,
        service_duration_minutes=service.duration_minutes,
        service_price_cents=service.price_cents,
        booking_channel=booking_channel,
    )

    appointment = Appointment(
        client_id=client_id,
        staff_id=staff_id,
        service_id=service_id,
        location_id=location_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        status="booked",
        booking_channel=booking_channel,
        is_first_visit=is_first_visit,
        lead_time_hours=lead_time_hours,
        no_show_risk_score=no_show_risk_score,
    )
    db.add(appointment)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise BookingConflictError("This time slot is no longer available") from exc

    await record_audit_event(
        db, user_id=client_id, action="appointment.created", entity="appointment", entity_id=appointment.id
    )
    await db.commit()
    await db.refresh(appointment)
    schedule_reminders(appointment)
    return appointment
