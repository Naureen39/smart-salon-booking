import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.db.models.appointment import Appointment
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.tasks.reminders import REMINDER_OFFSETS_HOURS, get_risk_tier, schedule_reminders


def _auth_header(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _make_appointment(risk_score: float, hours_until_start: float = 200) -> Appointment:
    return Appointment(
        id=uuid.uuid4(),
        scheduled_start=datetime.now(UTC) + timedelta(hours=hours_until_start),
        no_show_risk_score=risk_score,
        status="booked",
    )


@pytest.mark.parametrize(
    ("score", "expected_tier"),
    [(0.0, "low"), (0.29, "low"), (0.3, "medium"), (0.6, "medium"), (0.61, "high"), (0.95, "high")],
)
def test_get_risk_tier_boundaries(score: float, expected_tier: str) -> None:
    assert get_risk_tier(score) == expected_tier


def test_schedule_reminders_low_risk_schedules_one_task() -> None:
    appointment = _make_appointment(risk_score=0.1)
    with patch("app.tasks.reminders.send_appointment_reminder") as mock_task:
        schedule_reminders(appointment)
    assert mock_task.apply_async.call_count == len(REMINDER_OFFSETS_HOURS["low"])


def test_schedule_reminders_medium_risk_schedules_two_tasks() -> None:
    appointment = _make_appointment(risk_score=0.45)
    with patch("app.tasks.reminders.send_appointment_reminder") as mock_task:
        schedule_reminders(appointment)
    assert mock_task.apply_async.call_count == len(REMINDER_OFFSETS_HOURS["medium"])


def test_schedule_reminders_high_risk_schedules_three_tasks_with_correct_etas() -> None:
    appointment = _make_appointment(risk_score=0.9, hours_until_start=200)
    with patch("app.tasks.reminders.send_appointment_reminder") as mock_task:
        schedule_reminders(appointment)

    assert mock_task.apply_async.call_count == 3
    scheduled_etas = sorted(call.kwargs["eta"] for call in mock_task.apply_async.call_args_list)
    expected_etas = sorted(appointment.scheduled_start - timedelta(hours=h) for h in REMINDER_OFFSETS_HOURS["high"])
    assert scheduled_etas == expected_etas


def test_schedule_reminders_skips_offsets_already_in_the_past() -> None:
    # Only 10 hours until the appointment — the 72h and 24h high-risk offsets
    # would fall in the past, so only the 2h-before reminder should be queued.
    appointment = _make_appointment(risk_score=0.9, hours_until_start=10)
    with patch("app.tasks.reminders.send_appointment_reminder") as mock_task:
        schedule_reminders(appointment)
    assert mock_task.apply_async.call_count == 1


async def test_create_appointment_schedules_reminders(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC).replace(hour=9)
    # create_appointment now delegates to app.booking.create.create_booking, which is
    # where schedule_reminders is actually called from for the creation path.
    with patch("app.booking.create.schedule_reminders") as mock_schedule:
        response = await client.post(
            "/api/v1/appointments",
            json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
            headers=_auth_header(client_user),
        )
    assert response.status_code == 201
    assert mock_schedule.call_count == 1
    scheduled_appointment = mock_schedule.call_args[0][0]
    assert str(scheduled_appointment.id) == response.json()["id"]


async def test_reschedule_appointment_schedules_fresh_reminders(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC).replace(hour=10)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    new_start = start + timedelta(hours=1)
    with patch("app.api.v1.appointments.schedule_reminders") as mock_schedule:
        response = await client.put(
            f"/api/v1/appointments/{appointment_id}/reschedule",
            json={"scheduled_start": new_start.isoformat()},
            headers=_auth_header(client_user),
        )
    assert response.status_code == 200
    assert mock_schedule.call_count == 1
