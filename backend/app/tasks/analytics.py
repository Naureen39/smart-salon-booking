"""Nightly rollup job producing daily_booking_stats (docs plan §12) — powers
the admin dashboard's overview cards and trend charts from a small,
pre-aggregated table instead of scanning every appointment on each page load.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models.appointment import Appointment
from app.db.models.daily_booking_stats import DailyBookingStats
from app.db.models.service import Service
from app.tasks.celery_app import celery_app

settings = get_settings()


async def rollup_day(db: AsyncSession, target_date: date) -> DailyBookingStats:
    """Computes and upserts the rollup row for a single day. Pure DB-session
    logic, independent of Celery/asyncio wrapping, so it's directly testable."""
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    counts = (
        await db.execute(
            select(
                func.count(Appointment.id),
                func.coalesce(func.sum(case((Appointment.status == "completed", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.status == "cancelled", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.status == "no_show", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.booking_channel == "web", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.booking_channel == "chat", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.booking_channel == "voice", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Appointment.booking_channel == "admin", 1), else_=0)), 0),
            ).where(Appointment.scheduled_start >= day_start, Appointment.scheduled_start < day_end)
        )
    ).one()
    total, completed, cancelled, no_show, web, chat, voice, admin_channel = counts

    revenue_cents = (
        await db.execute(
            select(func.coalesce(func.sum(Service.price_cents), 0))
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .where(
                Appointment.scheduled_start >= day_start,
                Appointment.scheduled_start < day_end,
                Appointment.status == "completed",
            )
        )
    ).scalar_one()

    values = {
        "total_bookings": total,
        "completed_count": completed,
        "cancelled_count": cancelled,
        "no_show_count": no_show,
        "revenue_cents": revenue_cents,
        "web_count": web,
        "chat_count": chat,
        "voice_count": voice,
        "admin_count": admin_channel,
    }

    stmt = insert(DailyBookingStats).values(date=target_date, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyBookingStats.date],
        set_={**values, "updated_at": func.now()},
    )
    await db.execute(stmt)
    await db.commit()

    return await db.get_one(DailyBookingStats, target_date)


async def _rollup_day_fresh_engine(target_date: date) -> None:
    # A fresh engine per invocation — see app/tasks/reminders.py for why
    # Celery's sync-task-wrapping-asyncio.run model needs this rather than the
    # app's module-level engine.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as db:
            await rollup_day(db, target_date)
    finally:
        await engine.dispose()


@celery_app.task(name="analytics.rollup_daily_stats")
def rollup_daily_stats(target_date_iso: str | None = None) -> str:
    if target_date_iso:
        target_date = date.fromisoformat(target_date_iso)
    else:
        target_date = datetime.now(UTC).date() - timedelta(days=1)
    asyncio.run(_rollup_day_fresh_engine(target_date))
    return f"rolled up {target_date.isoformat()}"
