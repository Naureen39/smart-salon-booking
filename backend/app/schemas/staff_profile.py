import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

_WEEKDAY_KEYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_WINDOW_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


class StaffProfileBase(BaseModel):
    user_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    title: str | None = None
    bio: str | None = None
    working_hours: dict | None = None
    """e.g. {"mon": ["09:00-17:00"], ...} — each day maps to a list of
    "HH:MM-HH:MM" windows. Validated here (rather than left as a free-form
    dict) because a malformed value would otherwise pass creation silently
    and only surface as a 500 later, at booking time, when
    app.booking.availability parses it."""

    @field_validator("working_hours")
    @classmethod
    def _validate_working_hours(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        for day, windows in value.items():
            if day not in _WEEKDAY_KEYS:
                raise ValueError(f'"{day}" is not a valid weekday key (expected one of {sorted(_WEEKDAY_KEYS)})')
            if not isinstance(windows, list) or not all(isinstance(w, str) for w in windows):
                raise ValueError(f'working_hours["{day}"] must be a list of "HH:MM-HH:MM" strings')
            for window in windows:
                if not _WINDOW_RE.match(window):
                    raise ValueError(f'"{window}" is not a valid "HH:MM-HH:MM" window (e.g. "09:00-17:00")')
        return value


class StaffProfileCreate(StaffProfileBase):
    pass


class StaffProfileUpdate(StaffProfileBase):
    pass


class StaffProfileRead(StaffProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
