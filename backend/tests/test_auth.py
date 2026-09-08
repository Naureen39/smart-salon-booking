from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.db.models.user import User

settings = get_settings()


async def test_signup_creates_client_and_ignores_role_escalation(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "client@example.com",
            "password": "password123",
            "full_name": "Client User",
            "role": "admin",  # attempted role escalation — must be ignored
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "client"

    user = await db_session.scalar(select(User).where(User.email == "client@example.com"))
    assert user is not None
    assert user.role == "client"
    assert user.is_verified is False


async def test_signup_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "dupe@example.com", "password": "password123", "full_name": "Dupe User"}
    first = await client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


async def test_login_happy_path_and_me(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "loginme@example.com", "password": "password123", "full_name": "Login Me"},
    )

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "loginme@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    assert "refresh_token" in login_response.cookies

    me_response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "loginme@example.com"


async def test_login_invalid_credentials(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "badlogin@example.com", "password": "correctpass1", "full_name": "Bad Login"},
    )

    response = await client.post("/api/v1/auth/login", json={"email": "badlogin@example.com", "password": "wrongpass"})
    assert response.status_code == 401


async def test_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_refresh_rotates_token_and_old_one_is_invalid(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "refresher@example.com", "password": "password123", "full_name": "Refresher"},
    )
    await client.post("/api/v1/auth/login", json={"email": "refresher@example.com", "password": "password123"})

    old_refresh_cookie = client.cookies.get("refresh_token")
    assert old_refresh_cookie is not None

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]

    # Replaying the old (now-rotated-away) refresh token must fail.
    client.cookies.set("refresh_token", old_refresh_cookie)
    reuse_response = await client.post("/api/v1/auth/refresh")
    assert reuse_response.status_code == 401


async def test_refresh_without_cookie_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "logout@example.com", "password": "password123", "full_name": "Logout User"},
    )
    await client.post("/api/v1/auth/login", json={"email": "logout@example.com", "password": "password123"})

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


async def test_expired_access_token_is_rejected(client: AsyncClient) -> None:
    login_setup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "expiredtok@example.com", "password": "password123", "full_name": "Expired Tok"},
    )
    assert login_setup.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "expiredtok@example.com", "password": "password123"}
    )
    access_token = login_response.json()["access_token"]
    payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.jwt_algorithm])

    expired_payload = {
        **payload,
        "iat": datetime.now(UTC) - timedelta(hours=1),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


async def test_tampered_token_is_rejected(client: AsyncClient) -> None:
    forged_token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "role": "admin",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "wrong-secret-key",
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401


async def test_verify_email(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "verify@example.com", "password": "password123", "full_name": "Verify User"},
    )
    user = await db_session.scalar(select(User).where(User.email == "verify@example.com"))
    assert user is not None
    assert user.is_verified is False

    redis_client = get_redis_client()
    keys = await redis_client.keys("email_verify:*")
    token = None
    for key in keys:
        stored_user_id = await redis_client.get(key)
        if stored_user_id == str(user.id):
            token = key.split(":", 1)[1]
            break
    assert token is not None

    response = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert response.status_code == 200

    await db_session.refresh(user)
    assert user.is_verified is True


async def test_verify_email_rejects_unknown_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/verify-email?token=not-a-real-token")
    assert response.status_code == 400
