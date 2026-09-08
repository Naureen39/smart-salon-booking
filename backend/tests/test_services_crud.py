from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.models.user import User


async def test_public_can_list_but_not_create_services(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/services")
    assert list_response.status_code == 200
    assert list_response.json() == []

    create_response = await client.post(
        "/api/v1/services", json={"name": "Haircut", "duration_minutes": 30, "price_cents": 3000}
    )
    assert create_response.status_code == 401


async def test_admin_can_create_and_public_can_read_it_back(client: AsyncClient, admin_user: User) -> None:
    token = create_access_token(admin_user.id, admin_user.role)

    create_response = await client.post(
        "/api/v1/services",
        json={"name": "Haircut", "duration_minutes": 30, "price_cents": 3000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    service_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/services/{service_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Haircut"


async def test_non_admin_client_cannot_create_service(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "cantcreate@example.com", "password": "password123", "full_name": "Cant Create"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "cantcreate@example.com", "password": "password123"}
    )
    token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/services",
        json={"name": "Haircut", "duration_minutes": 30, "price_cents": 3000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_missing_service_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/services/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_admin_can_update_and_delete_service(client: AsyncClient, admin_user: User) -> None:
    token = create_access_token(admin_user.id, admin_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/services",
        json={"name": "Manicure", "duration_minutes": 45, "price_cents": 2500},
        headers=headers,
    )
    service_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/v1/services/{service_id}", json={"price_cents": 2800}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["price_cents"] == 2800
    assert update_response.json()["name"] == "Manicure"

    delete_response = await client.delete(f"/api/v1/services/{service_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/services/{service_id}")
    assert get_response.status_code == 404
