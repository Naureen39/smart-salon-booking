import uuid

from pydantic import BaseModel, ConfigDict


class StaffProfileBase(BaseModel):
    user_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    title: str | None = None
    bio: str | None = None
    working_hours: dict | None = None
    """e.g. {"mon": ["09:00-17:00"], ...}"""


class StaffProfileCreate(StaffProfileBase):
    pass


class StaffProfileUpdate(StaffProfileBase):
    pass


class StaffProfileRead(StaffProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
