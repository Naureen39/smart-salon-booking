from httpx import AsyncClient


async def test_login_rate_limit_returns_429_after_threshold(client: AsyncClient) -> None:
    payload = {"email": "ratelimit-login@example.com", "password": "wrongpass"}
    responses = [await client.post("/api/v1/auth/login", json=payload) for _ in range(12)]
    assert any(response.status_code == 429 for response in responses)


async def test_signup_rate_limit_returns_429_after_threshold(client: AsyncClient) -> None:
    responses = []
    for i in range(7):
        payload = {
            "email": f"ratelimit-signup-{i}@example.com",
            "password": "password123",
            "full_name": "Rate Limit Test",
        }
        responses.append(await client.post("/api/v1/auth/signup", json=payload))
    assert any(response.status_code == 429 for response in responses)
