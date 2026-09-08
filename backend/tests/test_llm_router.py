import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import llm_router as llm_router_module
from app.ai.llm_router import CANNED_JSON_FALLBACK, CANNED_TEXT_FALLBACK, LLMRouter
from app.ai.providers.base import LLMResponse, ProviderError
from app.core.redis import get_redis_client
from app.db.models.llm_usage import LlmUsage


class _FakeProvider:
    def __init__(self, name: str, responses: list) -> None:
        self.name = name
        self.model = f"{name}-fake-model"
        self._responses = list(responses)
        self.call_count = 0

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse:
        self.call_count += 1
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


async def test_router_returns_primary_response_on_success(db_session: AsyncSession) -> None:
    groq = _FakeProvider("groq", [LLMResponse(text="hello", tokens_in=3, tokens_out=2)])
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test")

    assert result == "hello"
    assert groq.call_count == 1
    assert gemini.call_count == 0


async def test_router_fails_over_to_gemini_on_groq_429(db_session: AsyncSession) -> None:
    groq = _FakeProvider(
        "groq",
        [ProviderError("429", retryable=True), ProviderError("429", retryable=True)],
    )
    gemini = _FakeProvider("gemini", [LLMResponse(text="hello from gemini", tokens_in=10, tokens_out=5)])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test")

    assert result == "hello from gemini"
    assert groq.call_count == 2  # one retry before failing over
    assert gemini.call_count == 1


async def test_router_does_not_retry_non_retryable_error(db_session: AsyncSession) -> None:
    groq = _FakeProvider("groq", [ProviderError("bad request", retryable=False)])
    gemini = _FakeProvider("gemini", [LLMResponse(text="gemini used", tokens_in=1, tokens_out=1)])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test")

    assert result == "gemini used"
    assert groq.call_count == 1  # no retry on a non-retryable error


async def test_router_falls_back_to_canned_text_when_both_providers_fail(db_session: AsyncSession) -> None:
    groq = _FakeProvider("groq", [ProviderError("500", retryable=True), ProviderError("500", retryable=True)])
    gemini = _FakeProvider("gemini", [ProviderError("500", retryable=True), ProviderError("500", retryable=True)])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test")

    assert result == CANNED_TEXT_FALLBACK


async def test_router_retries_then_falls_back_on_malformed_json(db_session: AsyncSession) -> None:
    groq = _FakeProvider(
        "groq",
        [
            LLMResponse(text="not json", tokens_in=10, tokens_out=5),
            LLMResponse(text="still not json", tokens_in=10, tokens_out=5),
        ],
    )
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test", json_mode=True)

    assert result == CANNED_JSON_FALLBACK
    assert groq.call_count == 2
    assert gemini.call_count == 0


async def test_router_recovers_after_json_retry(db_session: AsyncSession) -> None:
    groq = _FakeProvider(
        "groq",
        [
            LLMResponse(text="not json", tokens_in=10, tokens_out=5),
            LLMResponse(text='{"ok": true}', tokens_in=10, tokens_out=5),
        ],
    )
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    result = await router.complete(db_session, system="sys", user="hi", purpose="test", json_mode=True)

    assert result == '{"ok": true}'


async def test_router_logs_usage_for_successful_call(db_session: AsyncSession) -> None:
    groq = _FakeProvider("groq", [LLMResponse(text="hi", tokens_in=3, tokens_out=2)])
    gemini = _FakeProvider("gemini", [])
    router = LLMRouter(primary=groq, fallback=gemini)

    await router.complete(db_session, system="sys", user="hi", purpose="unit_test_purpose")

    rows = list(await db_session.scalars(select(LlmUsage).where(LlmUsage.purpose == "unit_test_purpose")))
    assert len(rows) == 1
    assert rows[0].provider == "groq"
    assert rows[0].tokens_in == 3
    assert rows[0].tokens_out == 2
    assert rows[0].success is True


async def test_router_logs_failed_attempts(db_session: AsyncSession) -> None:
    groq = _FakeProvider("groq", [ProviderError("boom", retryable=False)])
    gemini = _FakeProvider("gemini", [LLMResponse(text="ok", tokens_in=1, tokens_out=1)])
    router = LLMRouter(primary=groq, fallback=gemini)

    await router.complete(db_session, system="sys", user="hi", purpose="failure_logging_test")

    rows = list(await db_session.scalars(select(LlmUsage).where(LlmUsage.purpose == "failure_logging_test")))
    assert len(rows) == 2
    failed = next(r for r in rows if not r.success)
    succeeded = next(r for r in rows if r.success)
    assert failed.provider == "groq"
    assert succeeded.provider == "gemini"


async def test_router_proactively_skips_primary_when_over_daily_limit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(llm_router_module.DAILY_REQUEST_LIMITS, "groq", 1)

    groq = _FakeProvider("groq", [LLMResponse(text="should not be used", tokens_in=1, tokens_out=1)])
    gemini = _FakeProvider("gemini", [LLMResponse(text="gemini used", tokens_in=1, tokens_out=1)])
    router = LLMRouter(primary=groq, fallback=gemini)

    await get_redis_client().set(router._daily_count_key("groq"), "1")

    result = await router.complete(db_session, system="sys", user="hi", purpose="daily_limit_test")

    assert result == "gemini used"
    assert groq.call_count == 0
    assert gemini.call_count == 1
