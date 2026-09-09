import uuid
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.appointment import Appointment
from app.db.models.location import Location
from app.db.models.staff_profile import StaffProfile

SLOT_GRANULARITY_MINUTES = 15
ACTIVE_STATUSES = ("booked", "confirmed")

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class AvailableSlot:
    staff_id: uuid.UUID
    location_id: uuid.UUID | None
    start: datetime
    end: datetime


def _parse_window(window: str) -> tuple[time, time]:
    start_str, end_str = window.split("-")
    start_h, start_m = (int(part) for part in start_str.split(":"))
    end_h, end_m = (int(part) for part in end_str.split(":"))
    return time(start_h, start_m), time(end_h, end_m)


def _day_windows(working_hours: dict | None, target_date: date_type) -> list[tuple[time, time]]:
    if not working_hours:
        return []
    key = _WEEKDAY_KEYS[target_date.weekday()]
    windows = working_hours.get(key) or []
    return [_parse_window(window) for window in windows]


async def compute_available_slots(
    db: AsyncSession,
    *,
    target_date: date_type,
    duration_minutes: int,
    location_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
) -> list[AvailableSlot]:
    """Rule-based slot computation (§9.1's "no LLM needed" availability lookup):
    candidate staff's working_hours for the day, minus any active appointment
    they already have, sliced into SLOT_GRANULARITY_MINUTES-spaced candidate
    starts wide enough to fit the service's duration.
    """
    staff_query = select(StaffProfile)
    if staff_id is not None:
        staff_query = staff_query.where(StaffProfile.id == staff_id)
    elif location_id is not None:
        staff_query = staff_query.where(StaffProfile.location_id == location_id)

    staff_profiles = list(await db.scalars(staff_query))
    if not staff_profiles:
        return []

    # Resolved per staff member, not once for the whole call: a multi-location
    # business has staff whose working_hours are in *their own* location's
    # local time, not a single timezone shared by everyone. Callers that don't
    # (or can't) pre-filter to one location — the conversation orchestrator
    # never has — used to silently get every staff member's hours interpreted
    # as UTC, which is only correct by coincidence when a location's timezone
    # actually is UTC.
    referenced_location_ids = {staff.location_id for staff in staff_profiles if staff.location_id is not None}
    locations_by_id = (
        {loc.id: loc for loc in await db.scalars(select(Location).where(Location.id.in_(referenced_location_ids)))}
        if referenced_location_ids
        else {}
    )

    slots: list[AvailableSlot] = []
    for staff in staff_profiles:
        location = locations_by_id.get(staff.location_id) if staff.location_id else None
        tzinfo = ZoneInfo(location.timezone) if location is not None else ZoneInfo("UTC")

        windows = _day_windows(staff.working_hours, target_date)
        if not windows:
            continue

        day_start = datetime.combine(target_date, time.min, tzinfo=tzinfo)
        day_end = day_start + timedelta(days=1)

        existing = list(
            await db.scalars(
                select(Appointment).where(
                    Appointment.staff_id == staff.id,
                    Appointment.status.in_(ACTIVE_STATUSES),
                    Appointment.scheduled_start < day_end,
                    Appointment.scheduled_end > day_start,
                )
            )
        )

        for window_start, window_end in windows:
            cursor = datetime.combine(target_date, window_start, tzinfo=tzinfo)
            window_end_dt = datetime.combine(target_date, window_end, tzinfo=tzinfo)

            while cursor + timedelta(minutes=duration_minutes) <= window_end_dt:
                candidate_end = cursor + timedelta(minutes=duration_minutes)
                overlaps = any(
                    cursor < appt.scheduled_end and candidate_end > appt.scheduled_start for appt in existing
                )
                if not overlaps:
                    slots.append(
                        AvailableSlot(
                            staff_id=staff.id, location_id=staff.location_id, start=cursor, end=candidate_end
                        )
                    )
                cursor += timedelta(minutes=SLOT_GRANULARITY_MINUTES)

    slots.sort(key=lambda slot: (slot.start, str(slot.staff_id)))
    return slots
