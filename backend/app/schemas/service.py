import uuid

from pydantic import BaseModel, ConfigDict


class ServiceBase(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    duration_minutes: int
    price_cents: int
    image_url: str | None = None
    is_active: bool = True


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    duration_minutes: int | None = None
    price_cents: int | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ServiceRead(ServiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
