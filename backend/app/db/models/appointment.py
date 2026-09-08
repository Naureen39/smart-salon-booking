import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Appointment(Base):
    """The central booking record."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked','confirmed','completed','cancelled','no_show')", name="ck_appointments_status"
        ),
        CheckConstraint("booking_channel IN ('web','chat','voice','admin')", name="ck_appointments_channel"),
        # DB-level double-booking prevention (requires the btree_gist extension):
        # no two 'booked'/'confirmed' rows for the same staff may have overlapping
        # [scheduled_start, scheduled_end) ranges. This closes the race-condition
        # window an application-level pre-check can't (two concurrent requests
        # both checking "is this slot free?" before either has inserted).
        ExcludeConstraint(
            (literal_column("staff_id"), "="),
            (literal_column("tstzrange(scheduled_start, scheduled_end)"), "&&"),
            where=text("status IN ('booked','confirmed')"),
            using="gist",
            name="appointments_no_overlap",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"))
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"))
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="booked")
    booking_channel: Mapped[str | None] = mapped_column(String)
    is_first_visit: Mapped[bool] = mapped_column(Boolean, server_default="false")
    lead_time_hours: Mapped[float | None] = mapped_column(Numeric)
    """Hours between booking creation and appointment time."""
    no_show_risk_score: Mapped[float | None] = mapped_column(Numeric)
    """0.0-1.0, filled by the ML pipeline."""
    reminder_sent_at: Mapped[list[datetime] | None] = mapped_column(ARRAY(DateTime(timezone=True)))
    """Audit trail of reminder sends."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
