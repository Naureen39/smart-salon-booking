import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("scheduled_start must include a timezone")
    return value


class AppointmentCreate(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    scheduled_start: datetime
    booking_channel: str = "web"

    _validate_tz = field_validator("scheduled_start")(_require_timezone)


class AppointmentReschedule(BaseModel):
    scheduled_start: datetime

    _validate_tz = field_validator("scheduled_start")(_require_timezone)


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None
    staff_id: uuid.UUID | None
    service_id: uuid.UUID | None
    location_id: uuid.UUID | None
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    booking_channel: str | None
    is_first_visit: bool
    lead_time_hours: float | None
    no_show_risk_score: float | None
    created_at: datetime
    updated_at: datetime


class AvailableSlotRead(BaseModel):
    staff_id: uuid.UUID
    location_id: uuid.UUID | None
    start: datetime
    end: datetime
