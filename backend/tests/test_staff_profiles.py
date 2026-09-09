from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.models.user import User


async def test_malformed_working_hours_rejected_with_422(client: AsyncClient, admin_user: User) -> None:
    """Regression test for a gap found in manual end-to-end testing: a
    working_hours value shaped like {"mon": ["09:00", "18:00"]} (two bare
    times instead of one "HH:MM-HH:MM" range string) used to be accepted
    silently at creation and only crashed later, as an unhandled 500, the
    moment any client tried to book with that staff member.
    """
    token = create_access_token(admin_user.id, admin_user.role)

    response = await client.post(
        "/api/v1/staff",
        json={"title": "Bad Hours", "working_hours": {"mon": ["09:00", "18:00"]}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


async def test_invalid_weekday_key_rejected_with_422(client: AsyncClient, admin_user: User) -> None:
    token = create_access_token(admin_user.id, admin_user.role)

    response = await client.post(
        "/api/v1/staff",
        json={"title": "Bad Weekday", "working_hours": {"funday": ["09:00-17:00"]}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


async def test_well_formed_working_hours_accepted(client: AsyncClient, admin_user: User) -> None:
    token = create_access_token(admin_user.id, admin_user.role)

    response = await client.post(
        "/api/v1/staff",
        json={"title": "Good Hours", "working_hours": {"mon": ["09:00-13:00", "14:00-18:00"]}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["working_hours"] == {"mon": ["09:00-13:00", "14:00-18:00"]}
