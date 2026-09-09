"""Admin analytics endpoints (docs plan §12) — overview cards and trend
charts read from the daily_booking_stats rollup for speed; service/staff
breakdowns and the at-risk table are live queries (cheap enough at MVP
scale, and "at-risk upcoming appointments" specifically needs current data,
not a nightly snapshot). Every endpoint is role-gated *and* audit-logged
(docs plan §7.11: "admin-only analytics endpoints double-guarded").
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.audit import record_audit_event
from app.db.models.appointment import Appointment
from app.db.models.daily_booking_stats import DailyBookingStats
from app.db.models.llm_usage import LlmUsage
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analytics import (
    AtRiskAppointment,
    ChannelBreakdown,
    DailyStatsPoint,
    LlmUsagePoint,
    OverviewStats,
    ServicePopularity,
    StaffUtilization,
)
from app.tasks.reminders import get_risk_tier, send_appointment_reminder

router = APIRouter(prefix="/admin", tags=["admin"])

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@router.get("/ping")
async def admin_ping(_user: User = Depends(require_role("staff", "admin"))) -> dict[str, str]:
    """Minimal RBAC-protected route proving the require_role dependency works end to end."""
    return {"message": "admin access granted"}


async def require_admin_analytics_access(
    current_user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    await record_audit_event(
        db, user_id=current_user.id, action="admin.analytics_access", entity="analytics", entity_id=None
    )
    await db.commit()
    return current_user


def _parse_window_hours(window: str) -> float:
    start_str, end_str = window.split("-")
    start_h, start_m = (int(part) for part in start_str.split(":"))
    end_h, end_m = (int(part) for part in end_str.split(":"))
    return ((end_h * 60 + end_m) - (start_h * 60 + start_m)) / 60


def _compute_available_hours(working_hours: dict | None, period_start: date, period_end: date) -> float:
    if not working_hours:
        return 0.0
    total = 0.0
    current = period_start
    while current < period_end:
        windows = working_hours.get(_WEEKDAY_KEYS[current.weekday()]) or []
        total += sum(_parse_window_hours(window) for window in windows)
        current += timedelta(days=1)
    return total


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> OverviewStats:
    period_start = datetime.now(UTC).date() - timedelta(days=days)

    total_bookings, no_show_count = (
        await db.execute(
            select(
                func.coalesce(func.sum(DailyBookingStats.total_bookings), 0),
                func.coalesce(func.sum(DailyBookingStats.no_show_count), 0),
            ).where(DailyBookingStats.date >= period_start)
        )
    ).one()
    no_show_rate = (no_show_count / total_bookings) if total_bookings else 0.0

    period_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
    now = datetime.now(UTC)
    avg_lead_time = (
        await db.execute(
            select(func.avg(Appointment.lead_time_hours)).where(
                Appointment.scheduled_start >= period_start_dt,
                # Upper-bounded to match total_bookings/no_show_rate's window (the
                # daily_booking_stats rollup only ever covers already-elapsed days) —
                # without this, an unbounded query silently mixes in every future
                # booking, which can make a "0 bookings this period" card show a
                # large, unrelated average lead time next to it.
                Appointment.scheduled_start < now,
            )
        )
    ).scalar_one()

    revenue_at_risk = (
        await db.execute(
            select(func.coalesce(func.sum(Service.price_cents), 0))
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .where(
                Appointment.status.in_(("booked", "confirmed")),
                Appointment.scheduled_start > datetime.now(UTC),
                Appointment.no_show_risk_score > 0.6,
            )
        )
    ).scalar_one()

    return OverviewStats(
        period_days=days,
        total_bookings=total_bookings,
        no_show_rate=round(no_show_rate, 4),
        revenue_at_risk_cents=revenue_at_risk,
        avg_lead_time_hours=round(float(avg_lead_time or 0.0), 2),
    )


@router.get("/bookings-over-time", response_model=list[DailyStatsPoint])
async def get_bookings_over_time(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> list[DailyStatsPoint]:
    period_start = datetime.now(UTC).date() - timedelta(days=days)
    rows = await db.scalars(
        select(DailyBookingStats).where(DailyBookingStats.date >= period_start).order_by(DailyBookingStats.date)
    )
    return [
        DailyStatsPoint(
            date=row.date,
            total_bookings=row.total_bookings,
            no_show_count=row.no_show_count,
            no_show_rate=round(row.no_show_count / row.total_bookings, 4) if row.total_bookings else 0.0,
            revenue_cents=row.revenue_cents,
        )
        for row in rows
    ]


@router.get("/service-popularity", response_model=list[ServicePopularity])
async def get_service_popularity(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> list[ServicePopularity]:
    period_start_dt = datetime.combine(
        datetime.now(UTC).date() - timedelta(days=days), datetime.min.time(), tzinfo=UTC
    )
    # Upper-bounded to "now" (see the matching fix in get_overview) — without
    # this, every future-dated booking leaks into every period, so choosing a
    # different `days` window barely changes the result.
    rows = await db.execute(
        select(
            Service.id,
            Service.name,
            func.count(Appointment.id),
            func.coalesce(func.sum(Service.price_cents), 0),
        )
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.scheduled_start >= period_start_dt,
            Appointment.scheduled_start < datetime.now(UTC),
            Appointment.status != "cancelled",
        )
        .group_by(Service.id, Service.name)
        .order_by(func.count(Appointment.id).desc())
    )
    return [
        ServicePopularity(service_id=row[0], service_name=row[1], bookings=row[2], revenue_cents=row[3])
        for row in rows.all()
    ]


@router.get("/staff-utilization", response_model=list[StaffUtilization])
async def get_staff_utilization(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> list[StaffUtilization]:
    period_end = datetime.now(UTC).date()
    period_start = period_end - timedelta(days=days)
    period_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)

    staff_profiles = list(await db.scalars(select(StaffProfile)))
    results: list[StaffUtilization] = []
    for staff in staff_profiles:
        booked_seconds = (
            await db.execute(
                select(
                    func.coalesce(
                        func.sum(func.extract("epoch", Appointment.scheduled_end - Appointment.scheduled_start)), 0
                    )
                ).where(
                    Appointment.staff_id == staff.id,
                    Appointment.scheduled_start >= period_start_dt,
                    # Matches _compute_available_hours' own [period_start, period_end)
                    # exclusive range below, so booked_hours / available_hours stay
                    # comparable — otherwise a future booking inflates booked_hours
                    # for a window whose available_hours denominator never counted
                    # that day at all.
                    Appointment.scheduled_start < datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
                    Appointment.status != "cancelled",
                )
            )
        ).scalar_one()
        results.append(
            StaffUtilization(
                staff_id=staff.id,
                staff_title=staff.title,
                booked_hours=round(float(booked_seconds) / 3600, 2),
                available_hours=round(_compute_available_hours(staff.working_hours, period_start, period_end), 2),
            )
        )
    return results


@router.get("/channel-breakdown", response_model=ChannelBreakdown)
async def get_channel_breakdown(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> ChannelBreakdown:
    period_start = datetime.now(UTC).date() - timedelta(days=days)
    web, chat, voice, admin_channel = (
        await db.execute(
            select(
                func.coalesce(func.sum(DailyBookingStats.web_count), 0),
                func.coalesce(func.sum(DailyBookingStats.chat_count), 0),
                func.coalesce(func.sum(DailyBookingStats.voice_count), 0),
                func.coalesce(func.sum(DailyBookingStats.admin_count), 0),
            ).where(DailyBookingStats.date >= period_start)
        )
    ).one()
    return ChannelBreakdown(web=web, chat=chat, voice=voice, admin=admin_channel)


@router.get("/at-risk-appointments", response_model=list[AtRiskAppointment])
async def get_at_risk_appointments(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> list[AtRiskAppointment]:
    rows = await db.execute(
        select(Appointment, User, Service)
        .join(User, Appointment.client_id == User.id)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.status.in_(("booked", "confirmed")),
            Appointment.scheduled_start > datetime.now(UTC),
        )
        .order_by(Appointment.no_show_risk_score.desc().nulls_last())
        .limit(limit)
    )
    return [
        AtRiskAppointment(
            appointment_id=appointment.id,
            client_name=client.full_name,
            client_email=client.email,
            service_name=service.name,
            scheduled_start=appointment.scheduled_start,
            no_show_risk_score=float(appointment.no_show_risk_score or 0.0),
        )
        for appointment, client, service in rows.all()
    ]


@router.post("/appointments/{appointment_id}/send-reminder", status_code=status.HTTP_202_ACCEPTED)
async def send_manual_reminder(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_analytics_access),
) -> dict[str, str]:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    tier = get_risk_tier(appointment.no_show_risk_score or 0.0)
    send_appointment_reminder.apply_async(
        args=[str(appointment.id), 0, tier, appointment.scheduled_start.isoformat()],
        eta=datetime.now(UTC),
    )
    await record_audit_event(
        db,
        user_id=admin_user.id,
        action="admin.manual_reminder_sent",
        entity="appointment",
        entity_id=appointment.id,
    )
    await db.commit()
    return {"detail": "Reminder queued"}


@router.get("/llm-usage", response_model=list[LlmUsagePoint])
async def get_llm_usage(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_analytics_access),
) -> list[LlmUsagePoint]:
    period_start = datetime.now(UTC) - timedelta(days=days)
    day_expr = func.date(LlmUsage.created_at)
    rows = await db.execute(
        select(
            LlmUsage.provider,
            day_expr,
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.tokens_in), 0),
            func.coalesce(func.sum(LlmUsage.tokens_out), 0),
            func.coalesce(func.sum(case((LlmUsage.success.is_(True), 1), else_=0)), 0),
        )
        .where(LlmUsage.created_at >= period_start)
        .group_by(LlmUsage.provider, day_expr)
        .order_by(day_expr)
    )
    return [
        LlmUsagePoint(
            provider=row[0],
            date=row[1],
            total_calls=row[2],
            total_tokens_in=row[3],
            total_tokens_out=row[4],
            success_count=row[5],
        )
        for row in rows.all()
    ]
