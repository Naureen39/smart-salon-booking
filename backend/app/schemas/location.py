import uuid

from pydantic import BaseModel, ConfigDict


class LocationBase(BaseModel):
    name: str
    address: str | None = None
    timezone: str = "UTC"


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    timezone: str | None = None


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
