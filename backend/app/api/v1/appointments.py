import uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.booking.availability import compute_available_slots
from app.booking.create import BookingConflictError, ServiceNotFoundError, create_booking
from app.core.audit import record_audit_event
from app.db.models.appointment import Appointment
from app.db.models.service import Service
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentReschedule, AvailableSlotRead
from app.tasks.reminders import schedule_reminders

router = APIRouter(prefix="/appointments", tags=["appointments"])

NON_RESCHEDULABLE_STATUSES = ("cancelled", "completed", "no_show")


@router.get("/availability", response_model=list[AvailableSlotRead])
async def get_availability(
    service_id: uuid.UUID,
    date: date_type,
    location_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[AvailableSlotRead]:
    service = await db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    slots = await compute_available_slots(
        db,
        target_date=date,
        duration_minutes=service.duration_minutes,
        location_id=location_id,
        staff_id=staff_id,
    )
    return [AvailableSlotRead(staff_id=slot.staff_id, start=slot.start, end=slot.end) for slot in slots]


def _is_staff_or_admin(user: User) -> bool:
    return user.role in ("staff", "admin")


async def _get_owned_appointment(db: AsyncSession, appointment_id: uuid.UUID, current_user: User) -> Appointment:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appointment.client_id != current_user.id and not _is_staff_or_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your appointment")
    return appointment


@router.get("/me", response_model=list[AppointmentRead])
async def list_my_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    result = await db.scalars(
        select(Appointment).where(Appointment.client_id == current_user.id).order_by(Appointment.scheduled_start.desc())
    )
    return list(result)


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    return await _get_owned_appointment(db, appointment_id, current_user)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    try:
        return await create_booking(
            db,
            client_id=current_user.id,
            service_id=payload.service_id,
            staff_id=payload.staff_id,
            location_id=payload.location_id,
            scheduled_start=payload.scheduled_start,
            booking_channel=payload.booking_channel,
        )
    except ServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found") from exc
    except BookingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This time slot is no longer available"
        ) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = await _get_owned_appointment(db, appointment_id, current_user)
    if appointment.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment already cancelled")

    appointment.status = "cancelled"
    await record_audit_event(
        db, user_id=current_user.id, action="appointment.cancelled", entity="appointment", entity_id=appointment.id
    )
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.put("/{appointment_id}/reschedule", response_model=AppointmentRead)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = await _get_owned_appointment(db, appointment_id, current_user)
    if appointment.status in NON_RESCHEDULABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment can no longer be rescheduled")

    duration = appointment.scheduled_end - appointment.scheduled_start
    old_start = appointment.scheduled_start

    appointment.scheduled_start = payload.scheduled_start
    appointment.scheduled_end = payload.scheduled_start + duration

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This time slot is no longer available"
        ) from exc

    await record_audit_event(
        db,
        user_id=current_user.id,
        action="appointment.rescheduled",
        entity="appointment",
        entity_id=appointment.id,
        metadata={"old_start": old_start.isoformat(), "new_start": payload.scheduled_start.isoformat()},
    )
    await db.commit()
    await db.refresh(appointment)
    schedule_reminders(appointment)
    return appointment
