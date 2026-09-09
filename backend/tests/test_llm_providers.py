import json

import httpx
import pytest

from app.ai.providers.base import ProviderError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.groq_provider import GroqProvider


def _transport(status_code: int, json_body: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)

    return httpx.MockTransport(handler)


async def test_groq_provider_parses_successful_response() -> None:
    transport = _transport(
        200,
        {"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    )
    provider = GroqProvider(api_key="test-key", transport=transport)

    response = await provider.complete("sys", "hi", max_tokens=100, json_mode=False)

    assert response.text == "hello"
    assert response.tokens_in == 10
    assert response.tokens_out == 5


async def test_groq_provider_requests_low_reasoning_effort() -> None:
    """Regression test for a real bug found in manual end-to-end testing: the
    default model (gpt-oss-20b) is a reasoning model that can spend its
    entire max_tokens budget on a hidden reasoning trace, especially when the
    prompt has a numeric constraint like "under 40 words", and return blank
    visible content despite a 200 response. Requesting low reasoning effort
    fixed it (observed ~130 reasoning tokens dropping to single digits).
    """
    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    provider = GroqProvider(api_key="test-key", transport=httpx.MockTransport(handler))
    await provider.complete("sys", "hi", max_tokens=100, json_mode=False)

    assert captured_payload.get("reasoning_effort") == "low"


async def test_groq_provider_raises_retryable_error_on_429() -> None:
    provider = GroqProvider(api_key="test-key", transport=_transport(429, {"error": "rate limited"}))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("sys", "hi", max_tokens=100, json_mode=False)
    assert exc_info.value.retryable is True


async def test_groq_provider_raises_retryable_error_on_500() -> None:
    provider = GroqProvider(api_key="test-key", transport=_transport(500, {"error": "server error"}))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("sys", "hi", max_tokens=100, json_mode=False)
    assert exc_info.value.retryable is True


async def test_groq_provider_raises_non_retryable_error_on_400() -> None:
    provider = GroqProvider(api_key="test-key", transport=_transport(400, {"error": "bad request"}))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("sys", "hi", max_tokens=100, json_mode=False)
    assert exc_info.value.retryable is False


async def test_gemini_provider_parses_successful_response() -> None:
    transport = _transport(
        200,
        {
            "candidates": [{"content": {"parts": [{"text": "hi from gemini"}]}}],
            "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
        },
    )
    provider = GeminiProvider(api_key="test-key", transport=transport)

    response = await provider.complete("sys", "hi", max_tokens=100, json_mode=False)

    assert response.text == "hi from gemini"
    assert response.tokens_in == 8
    assert response.tokens_out == 4


async def test_gemini_provider_raises_retryable_error_on_429() -> None:
    provider = GeminiProvider(api_key="test-key", transport=_transport(429, {"error": "rate limited"}))

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete("sys", "hi", max_tokens=100, json_mode=False)
    assert exc_info.value.retryable is True
