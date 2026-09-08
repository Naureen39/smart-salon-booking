from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models.user import User


async def test_admin_ping_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/ping")
    assert response.status_code == 401


async def test_admin_ping_rejects_client_role(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "plainclient@example.com", "password": "password123", "full_name": "Plain Client"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "plainclient@example.com", "password": "password123"}
    )
    token = login.json()["access_token"]

    response = await client.get("/api/v1/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_ping_allows_admin_role(client: AsyncClient, admin_user: User) -> None:
    token = create_access_token(admin_user.id, admin_user.role)
    response = await client.get("/api/v1/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"message": "admin access granted"}


async def test_role_claim_in_stale_token_is_reverified_against_db(
    client: AsyncClient, admin_user: User, db_session: AsyncSession
) -> None:
    """A token minted while the user was an admin must stop granting admin access
    once the DB row's role changes — require_role re-checks the DB, not the JWT claim."""
    token = create_access_token(admin_user.id, "admin")

    admin_user.role = "client"
    await db_session.commit()

    response = await client.get("/api/v1/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
