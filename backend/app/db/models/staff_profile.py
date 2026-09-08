import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StaffProfile(Base):
    """A staff member's bookable profile, linked to a `users` row with role='staff'."""

    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    title: Mapped[str | None] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(String)
    working_hours: Mapped[dict | None] = mapped_column(JSONB)
    """e.g. {"mon": ["09:00-17:00"], ...}"""
