import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models.audit_log import AuditLog
from app.db.models.location import Location
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _slot_at(target_date: date, hour: int) -> datetime:
    return datetime.combine(target_date, datetime.min.time(), tzinfo=UTC).replace(hour=hour)


async def test_availability_returns_slots_within_working_hours(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date
) -> None:
    response = await client.get(
        "/api/v1/appointments/availability",
        params={"service_id": str(service.id), "date": target_date.isoformat()},
    )
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) > 0
    assert all(slot["staff_id"] == str(staff.id) for slot in slots)


async def test_availability_returns_nothing_outside_working_hours(
    client: AsyncClient, service: Service, staff: StaffProfile
) -> None:
    other_day = date.today() + timedelta(days=8)
    response = await client.get(
        "/api/v1/appointments/availability",
        params={"service_id": str(service.id), "date": other_day.isoformat()},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_create_appointment_computes_fields(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = _slot_at(target_date, 10)
    response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["is_first_visit"] is True
    assert body["lead_time_hours"] > 0
    assert 0.0 <= body["no_show_risk_score"] <= 1.0

    parsed_start = datetime.fromisoformat(body["scheduled_start"])
    parsed_end = datetime.fromisoformat(body["scheduled_end"])
    assert (parsed_end - parsed_start) == timedelta(minutes=service.duration_minutes)


async def test_appointment_location_is_derived_from_staff_not_caller(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    """Regression test: location_id used to be whatever the caller passed in
    the request body (or omitted), independent of the chosen staff member's
    actual assigned location — allowing a mismatched or missing value on the
    stored appointment. It's now always derived server-side from the staff
    profile, so passing an unrelated location_id in the payload has no effect.
    """
    start = _slot_at(target_date, 11)
    response = await client.post(
        "/api/v1/appointments",
        json={
            "service_id": str(service.id),
            "staff_id": str(staff.id),
            "location_id": str(uuid.uuid4()),  # an unrelated id — must be ignored
            "scheduled_start": start.isoformat(),
        },
        headers=_auth_header(client_user),
    )
    assert response.status_code == 201
    assert response.json()["location_id"] == str(staff.location_id)


async def test_availability_uses_staff_own_location_timezone(
    client: AsyncClient, db_session: AsyncSession, service: Service, target_date: date
) -> None:
    """Regression test for a severe bug found in manual end-to-end testing:
    compute_available_slots interpreted every staff member's working_hours as
    UTC unless the caller pre-filtered to a single location_id — which the
    conversation orchestrator never did — so a non-UTC salon's "9:00 AM" slot
    was actually computed at 9:00 AM UTC, silently wrong by the location's
    offset for every chat/voice booking (correct only by coincidence for a
    UTC-timezoned location, which is all the other fixtures use).
    """
    ny_location = Location(name="NYC Branch", timezone="America/New_York")
    db_session.add(ny_location)
    await db_session.commit()
    await db_session.refresh(ny_location)

    weekday_keys = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    ny_staff = StaffProfile(
        location_id=ny_location.id,
        title="NYC Stylist",
        working_hours={weekday_keys[target_date.weekday()]: ["09:00-17:00"]},
    )
    db_session.add(ny_staff)
    await db_session.commit()
    await db_session.refresh(ny_staff)

    response = await client.get(
        "/api/v1/appointments/availability",
        params={"service_id": str(service.id), "date": target_date.isoformat()},
    )
    assert response.status_code == 200
    ny_slots = [slot for slot in response.json() if slot["staff_id"] == str(ny_staff.id)]
    assert ny_slots

    first_start = datetime.fromisoformat(ny_slots[0]["start"])
    # 9:00 AM America/New_York is 13:00 or 14:00 UTC depending on DST — never
    # 09:00 UTC, which is what the bug produced. The response keeps the
    # location's own offset rather than normalizing to UTC, so convert before
    # comparing.
    assert first_start.astimezone(UTC).hour in (13, 14)
    assert ny_slots[0]["location_id"] == str(ny_location.id)


async def test_availability_excludes_booked_slots(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = _slot_at(target_date, 9)
    booking_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert booking_response.status_code == 201

    response = await client.get(
        "/api/v1/appointments/availability",
        params={"service_id": str(service.id), "date": target_date.isoformat()},
    )
    slots = response.json()
    assert all(datetime.fromisoformat(slot["start"]) != start for slot in slots)


async def test_second_booking_is_not_first_visit(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start1 = _slot_at(target_date, 9)
    first = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start1.isoformat()},
        headers=_auth_header(client_user),
    )
    assert first.status_code == 201

    start2 = start1 + timedelta(days=1)
    second = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start2.isoformat()},
        headers=_auth_header(client_user),
    )
    assert second.status_code == 201
    assert second.json()["is_first_visit"] is False


async def test_overlapping_booking_is_rejected(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = _slot_at(target_date, 11)
    first = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert first.status_code == 201

    overlapping_start = start + timedelta(minutes=10)
    second = await client.post(
        "/api/v1/appointments",
        json={
            "service_id": str(service.id),
            "staff_id": str(staff.id),
            "scheduled_start": overlapping_start.isoformat(),
        },
        headers=_auth_header(client_user),
    )
    assert second.status_code == 409


async def test_cancel_frees_the_slot(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = _slot_at(target_date, 13)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    cancel_response = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel", headers=_auth_header(client_user)
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    rebook_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert rebook_response.status_code == 201


async def test_cancelling_twice_is_rejected(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    start = _slot_at(target_date, 12)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    await client.post(f"/api/v1/appointments/{appointment_id}/cancel", headers=_auth_header(client_user))
    second_cancel = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel", headers=_auth_header(client_user)
    )
    assert second_cancel.status_code == 400


async def test_reschedule_updates_time_and_writes_audit_log(
    client: AsyncClient,
    service: Service,
    staff: StaffProfile,
    target_date: date,
    client_user: User,
    db_session: AsyncSession,
) -> None:
    start = _slot_at(target_date, 14)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    new_start = start + timedelta(hours=1)
    reschedule_response = await client.put(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"scheduled_start": new_start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert reschedule_response.status_code == 200
    assert datetime.fromisoformat(reschedule_response.json()["scheduled_start"]) == new_start

    audit_rows = list(
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity == "appointment",
                AuditLog.entity_id == uuid.UUID(appointment_id),
                AuditLog.action == "appointment.rescheduled",
            )
        )
    )
    assert len(audit_rows) == 1


async def test_reschedule_into_conflicting_slot_is_rejected(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    first_start = _slot_at(target_date, 9)
    second_start = _slot_at(target_date, 15)

    await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": first_start.isoformat()},
        headers=_auth_header(client_user),
    )
    second = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": second_start.isoformat()},
        headers=_auth_header(client_user),
    )
    second_id = second.json()["id"]

    reschedule_response = await client.put(
        f"/api/v1/appointments/{second_id}/reschedule",
        json={"scheduled_start": first_start.isoformat()},
        headers=_auth_header(client_user),
    )
    assert reschedule_response.status_code == 409


async def test_appointment_creation_requires_auth(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date
) -> None:
    start = _slot_at(target_date, 16)
    response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
    )
    assert response.status_code == 401


async def test_client_cannot_view_others_appointment(
    client: AsyncClient,
    service: Service,
    staff: StaffProfile,
    target_date: date,
    client_user: User,
    db_session: AsyncSession,
) -> None:
    start = _slot_at(target_date, 16)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    other_user = User(
        email="otherclient@example.com",
        hashed_password=hash_password("password123"),
        full_name="Other Client",
        role="client",
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    response = await client.get(f"/api/v1/appointments/{appointment_id}", headers=_auth_header(other_user))
    assert response.status_code == 403


async def test_admin_can_view_any_appointment(
    client: AsyncClient,
    service: Service,
    staff: StaffProfile,
    target_date: date,
    client_user: User,
    admin_user: User,
) -> None:
    start = _slot_at(target_date, 16)
    create_response = await client.post(
        "/api/v1/appointments",
        json={"service_id": str(service.id), "staff_id": str(staff.id), "scheduled_start": start.isoformat()},
        headers=_auth_header(client_user),
    )
    appointment_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/appointments/{appointment_id}", headers=_auth_header(admin_user))
    assert response.status_code == 200
