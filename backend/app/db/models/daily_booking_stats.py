from datetime import date as date_type
from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyBookingStats(Base):
    """Nightly rollup of booking activity per day (docs plan §12) — backs the
    admin dashboard's overview cards and trend charts without scanning every
    appointment on each page load (the plan's own "<1s from a materialized/
    cached query" performance target)."""

    __tablename__ = "daily_booking_stats"

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    total_bookings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    no_show_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    web_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chat_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    voice_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    admin_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
