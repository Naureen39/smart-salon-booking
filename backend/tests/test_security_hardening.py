import asyncio
import base64
import json
import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models.audit_log import AuditLog
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


async def test_none_algorithm_jwt_is_rejected(client: AsyncClient) -> None:
    """A classic JWT library vulnerability class: if a server ever accepted a
    token whose header claims alg=none (no signature), any attacker could
    forge arbitrary claims. decode_token() pins algorithms=[HS256] explicitly,
    which should make jose reject this outright.

    python-jose's own jwt.encode() refuses to build a "none"-alg token at all
    (raises JWSError) — but a real attacker wouldn't go through that API
    either, they'd hand-craft the token bytes, so that's what this test does.
    """
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "role": "admin",
        "type": "access",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
    }
    forged_token = (
        f"{_base64url_encode(json.dumps(header).encode())}."
        f"{_base64url_encode(json.dumps(payload).encode())}."
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401


async def test_login_rejects_sql_injection_shaped_email_at_validation(client: AsyncClient) -> None:
    """Pydantic's EmailStr rejects this before it ever reaches a query — a
    second line of defense on top of the ORM's parameterized queries."""
    response = await client.post("/api/v1/auth/login", json={"email": "' OR '1'='1", "password": "anything"})
    assert response.status_code == 422


async def test_delete_my_data_anonymizes_and_deactivates_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "todelete@example.com", "password": "password123", "full_name": "To Delete"},
    )
    user_id = uuid.UUID(signup.json()["id"])

    login = await client.post(
        "/api/v1/auth/login", json={"email": "todelete@example.com", "password": "password123"}
    )
    token = login.json()["access_token"]

    delete_response = await client.delete("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 204

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.email != "todelete@example.com"
    assert user.full_name == "Deleted User"
    assert user.phone is None
    assert user.is_active is False

    audit_rows = list(
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "user.self_deleted", AuditLog.entity_id == user_id)
        )
    )
    assert len(audit_rows) == 1

    # The account is deactivated — even a still-valid access token must stop working.
    me_response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401


async def test_concurrent_booking_requests_for_same_slot_only_one_succeeds(
    client: AsyncClient, service: Service, staff: StaffProfile, target_date: date, client_user: User
) -> None:
    """Load-tests the double-booking guarantee under real concurrency (docs
    plan §14 Phase 11 item 4) — several requests for the identical slot fired
    at once, relying on the Phase 2 DB-level exclusion constraint (not an
    app-level pre-check, which can't close this race) to let exactly one win.
    """
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC).replace(hour=14)
    payload = {
        "service_id": str(service.id),
        "staff_id": str(staff.id),
        "scheduled_start": start.isoformat(),
    }
    headers = _auth_header(client_user)

    responses = await asyncio.gather(
        *[client.post("/api/v1/appointments", json=payload, headers=headers) for _ in range(5)]
    )

    success_count = sum(1 for response in responses if response.status_code == 201)
    conflict_count = sum(1 for response in responses if response.status_code == 409)
    assert success_count == 1
    assert conflict_count == 4
