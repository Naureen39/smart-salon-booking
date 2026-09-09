import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.audit_log import AuditLog
from app.db.models.daily_booking_stats import DailyBookingStats
from app.db.models.llm_usage import LlmUsage
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.tasks.analytics import rollup_day


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_appointment(
    *,
    client_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_id: uuid.UUID,
    start: datetime,
    status: str = "completed",
    channel: str = "web",
    risk: float = 0.1,
    lead_time_hours: float = 24.0,
) -> Appointment:
    return Appointment(
        id=uuid.uuid4(),
        client_id=client_id,
        staff_id=staff_id,
        service_id=service_id,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        status=status,
        booking_channel=channel,
        no_show_risk_score=risk,
        is_first_visit=False,
        lead_time_hours=lead_time_hours,
    )


async def test_rollup_day_aggregates_counts_and_revenue(
    db_session: AsyncSession, client_user: User, staff: StaffProfile, service: Service
) -> None:
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)

    db_session.add_all(
        [
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=day_start.replace(hour=9),
                status="completed",
                channel="web",
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=day_start.replace(hour=10),
                status="no_show",
                channel="chat",
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=day_start.replace(hour=11),
                status="cancelled",
                channel="voice",
            ),
        ]
    )
    await db_session.commit()

    stats = await rollup_day(db_session, target_date)

    assert stats.total_bookings == 3
    assert stats.completed_count == 1
    assert stats.no_show_count == 1
    assert stats.cancelled_count == 1
    assert stats.revenue_cents == service.price_cents
    assert stats.web_count == 1
    assert stats.chat_count == 1
    assert stats.voice_count == 1


async def test_rollup_day_is_idempotent_on_rerun(
    db_session: AsyncSession, client_user: User, staff: StaffProfile, service: Service
) -> None:
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    db_session.add(
        _make_appointment(
            client_id=client_user.id, staff_id=staff.id, service_id=service.id, start=day_start.replace(hour=9)
        )
    )
    await db_session.commit()

    await rollup_day(db_session, target_date)
    stats = await rollup_day(db_session, target_date)

    rows = list(await db_session.scalars(select(DailyBookingStats).where(DailyBookingStats.date == target_date)))
    assert len(rows) == 1
    assert stats.total_bookings == 1


async def test_admin_analytics_endpoints_reject_non_admin(client: AsyncClient, client_user: User) -> None:
    for path in ("/api/v1/admin/overview", "/api/v1/admin/bookings-over-time", "/api/v1/admin/at-risk-appointments"):
        response = await client.get(path, headers=_auth_header(client_user))
        assert response.status_code == 403


async def test_overview_reflects_rollup_data(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    db_session.add(
        _make_appointment(
            client_id=client_user.id, staff_id=staff.id, service_id=service.id, start=day_start.replace(hour=9)
        )
    )
    await db_session.commit()
    await rollup_day(db_session, target_date)

    response = await client.get("/api/v1/admin/overview?days=30", headers=_auth_header(admin_user))
    assert response.status_code == 200
    assert response.json()["total_bookings"] == 1


async def test_overview_avg_lead_time_excludes_future_bookings(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    """Regression test for a gap found in manual end-to-end testing:
    avg_lead_time_hours had no upper bound on scheduled_start, so a booking
    made today for two weeks from now (which the daily_booking_stats rollup,
    scoped to already-elapsed days, correctly excludes from total_bookings)
    was still pulled into the average lead time — producing a contradictory
    overview card ("0 bookings" next to a large average lead time).
    """
    past_date = (datetime.now(UTC) - timedelta(days=1)).date()
    past_start = datetime.combine(past_date, datetime.min.time(), tzinfo=UTC).replace(hour=9)
    db_session.add(
        _make_appointment(
            client_id=client_user.id,
            staff_id=staff.id,
            service_id=service.id,
            start=past_start,
            lead_time_hours=48.0,
        )
    )
    db_session.add(
        _make_appointment(
            client_id=client_user.id,
            staff_id=staff.id,
            service_id=service.id,
            start=datetime.now(UTC) + timedelta(days=14),
            status="booked",
            lead_time_hours=336.0,
        )
    )
    await db_session.commit()
    await rollup_day(db_session, past_date)

    response = await client.get("/api/v1/admin/overview?days=30", headers=_auth_header(admin_user))

    assert response.status_code == 200
    assert response.json()["avg_lead_time_hours"] == 48.0


async def test_bookings_over_time_returns_rollup_points(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    db_session.add(
        _make_appointment(
            client_id=client_user.id,
            staff_id=staff.id,
            service_id=service.id,
            start=day_start.replace(hour=9),
            status="no_show",
        )
    )
    await db_session.commit()
    await rollup_day(db_session, target_date)

    response = await client.get("/api/v1/admin/bookings-over-time?days=30", headers=_auth_header(admin_user))
    assert response.status_code == 200
    matching = [point for point in response.json() if point["date"] == target_date.isoformat()]
    assert len(matching) == 1
    assert matching[0]["total_bookings"] == 1
    assert matching[0]["no_show_count"] == 1
    assert matching[0]["no_show_rate"] == 1.0


async def test_service_popularity_counts_bookings(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    start = datetime.now(UTC) - timedelta(days=1)
    db_session.add_all(
        [
            _make_appointment(client_id=client_user.id, staff_id=staff.id, service_id=service.id, start=start),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=start + timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/service-popularity?days=30", headers=_auth_header(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["service_name"] == service.name
    assert body[0]["bookings"] == 2


async def test_service_popularity_excludes_future_bookings(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    """Regression test for a gap found in manual end-to-end testing: this
    query had no upper bound on scheduled_start, so a booking made for two
    weeks out counted toward every `days` window equally — the period
    selector barely changed the result once any future bookings existed.
    """
    db_session.add_all(
        [
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=datetime.now(UTC) - timedelta(days=1),
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=datetime.now(UTC) + timedelta(days=14),
                status="booked",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/service-popularity?days=30", headers=_auth_header(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["bookings"] == 1


async def test_staff_utilization_computes_booked_and_available_hours(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    start = datetime.now(UTC) - timedelta(days=1)
    db_session.add(_make_appointment(client_id=client_user.id, staff_id=staff.id, service_id=service.id, start=start))
    await db_session.commit()

    # days=8 guarantees the window includes a day 7 days back from today, which
    # shares today's weekday — the only weekday the `staff` fixture configures
    # working_hours for (see conftest's `staff`/`target_date` fixtures).
    response = await client.get("/api/v1/admin/staff-utilization?days=8", headers=_auth_header(admin_user))
    assert response.status_code == 200
    matching = [row for row in response.json() if row["staff_id"] == str(staff.id)]
    assert len(matching) == 1
    assert matching[0]["booked_hours"] == pytest.approx(0.5, abs=0.01)
    assert matching[0]["available_hours"] == pytest.approx(8.0, abs=0.01)


async def test_staff_utilization_excludes_future_bookings(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    """Regression test: booked_hours had no upper bound on scheduled_start, so
    a far-future booking inflated it while available_hours (which only ever
    counts days strictly before today) stayed the same — a staff member could
    show over 100% utilization from bookings that haven't happened yet.
    """
    db_session.add_all(
        [
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=datetime.now(UTC) - timedelta(days=1),
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=datetime.now(UTC) + timedelta(days=14),
                status="booked",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/staff-utilization?days=8", headers=_auth_header(admin_user))

    assert response.status_code == 200
    matching = [row for row in response.json() if row["staff_id"] == str(staff.id)]
    assert len(matching) == 1
    assert matching[0]["booked_hours"] == pytest.approx(0.5, abs=0.01)


async def test_channel_breakdown_sums_rollup(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    target_date = (datetime.now(UTC) - timedelta(days=1)).date()
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    db_session.add_all(
        [
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=day_start.replace(hour=9),
                channel="web",
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=day_start.replace(hour=10),
                channel="voice",
            ),
        ]
    )
    await db_session.commit()
    await rollup_day(db_session, target_date)

    response = await client.get("/api/v1/admin/channel-breakdown?days=30", headers=_auth_header(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert body["web"] == 1
    assert body["voice"] == 1


async def test_at_risk_appointments_orders_by_risk_score_desc(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    future = datetime.now(UTC) + timedelta(days=3)
    db_session.add_all(
        [
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=future,
                status="booked",
                risk=0.2,
            ),
            _make_appointment(
                client_id=client_user.id,
                staff_id=staff.id,
                service_id=service.id,
                start=future + timedelta(hours=1),
                status="booked",
                risk=0.9,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/at-risk-appointments", headers=_auth_header(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 2
    assert body[0]["no_show_risk_score"] >= body[1]["no_show_risk_score"]


async def test_send_manual_reminder_queues_task_and_logs_audit(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
    client_user: User,
    staff: StaffProfile,
    service: Service,
) -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    appointment = _make_appointment(
        client_id=client_user.id, staff_id=staff.id, service_id=service.id, start=future, status="booked"
    )
    db_session.add(appointment)
    await db_session.commit()

    with patch("app.api.v1.admin_analytics.send_appointment_reminder") as mock_task:
        response = await client.post(
            f"/api/v1/admin/appointments/{appointment.id}/send-reminder", headers=_auth_header(admin_user)
        )
    assert response.status_code == 202
    assert mock_task.apply_async.call_count == 1

    audit_rows = list(
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "admin.manual_reminder_sent", AuditLog.entity_id == appointment.id
            )
        )
    )
    assert len(audit_rows) == 1


async def test_send_manual_reminder_404_for_missing_appointment(client: AsyncClient, admin_user: User) -> None:
    response = await client.post(
        f"/api/v1/admin/appointments/{uuid.uuid4()}/send-reminder", headers=_auth_header(admin_user)
    )
    assert response.status_code == 404


async def test_llm_usage_aggregates_by_provider_and_day(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
) -> None:
    db_session.add_all(
        [
            LlmUsage(
                provider="groq", model="m", purpose="test", tokens_in=10, tokens_out=5, latency_ms=100, success=True
            ),
            LlmUsage(
                provider="groq", model="m", purpose="test", tokens_in=20, tokens_out=8, latency_ms=120, success=False
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/llm-usage?days=7", headers=_auth_header(admin_user))
    assert response.status_code == 200
    groq_rows = [row for row in response.json() if row["provider"] == "groq"]
    assert len(groq_rows) == 1
    assert groq_rows[0]["total_calls"] == 2
    assert groq_rows[0]["total_tokens_in"] == 30
    assert groq_rows[0]["success_count"] == 1


async def test_analytics_access_is_audit_logged(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
) -> None:
    await client.get("/api/v1/admin/overview", headers=_auth_header(admin_user))
    rows = list(await db_session.scalars(select(AuditLog).where(AuditLog.action == "admin.analytics_access")))
    assert len(rows) >= 1
