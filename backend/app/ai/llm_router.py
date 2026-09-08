"""Dual-LLM router (Groq primary, Gemini fallback) per docs plan §9.4:
automatic failover on a retryable provider error (429/5xx), proactive
switching once a provider's daily request budget is spent, one retry on
malformed JSON-mode output before a canned fallback, and per-call usage
logging to llm_usage for cost/quota observability.

json_mode validation here is deliberately generic (syntactically valid JSON)
— this router is provider- and purpose-agnostic. A caller that needs a
specific shape (e.g. the Phase 7 conversation orchestrator's
{"slot_updates": ..., "reply_text": ...}) validates that on top of what this
returns, with its own Pydantic schema.
"""

import asyncio
import json
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMProvider, LLMResponse, ProviderError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.groq_provider import GroqProvider
from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.db.models.llm_usage import LlmUsage

settings = get_settings()

CANNED_TEXT_FALLBACK = (
    "Sorry, I'm having trouble reaching our assistant right now. A team member will follow up with you shortly."
)
CANNED_JSON_FALLBACK = '{"slot_updates": {}, "reply_text": "Sorry, could you rephrase that?"}'

STRICT_JSON_INSTRUCTION = "\n\nIMPORTANT: Respond with ONLY a single valid JSON object. No prose, no markdown."

DAILY_REQUEST_LIMITS: dict[str, int] = {
    "groq": settings.groq_daily_request_limit,
    "gemini": settings.gemini_daily_request_limit,
}


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
    except (TypeError, ValueError):
        return False
    return True


class LLMRouter:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def _daily_count_key(self, provider_name: str) -> str:
        today = datetime.now(UTC).date().isoformat()
        return f"llm_usage_count:{provider_name}:{today}"

    async def _is_over_daily_limit(self, provider_name: str) -> bool:
        limit = DAILY_REQUEST_LIMITS.get(provider_name)
        if not limit:
            return False
        count = await get_redis_client().get(self._daily_count_key(provider_name))
        return int(count or 0) >= limit

    async def _increment_daily_count(self, provider_name: str) -> None:
        redis_client = get_redis_client()
        key = self._daily_count_key(provider_name)
        await redis_client.incr(key)
        await redis_client.expire(key, 60 * 60 * 26)  # a little over a day — self-cleaning

    async def _log_usage(
        self,
        db: AsyncSession,
        *,
        provider: str,
        model: str,
        purpose: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        db.add(
            LlmUsage(
                provider=provider,
                model=model,
                purpose=purpose,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                success=success,
                error=error,
            )
        )
        await db.commit()

    async def _try_provider(
        self,
        db: AsyncSession,
        provider: LLMProvider,
        *,
        system: str,
        user: str,
        purpose: str,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMResponse | None:
        """Tries `provider` up to twice — one retry on a retryable failure,
        with a brief backoff — logging every attempt. Returns None if the
        provider never succeeds."""
        for attempt in range(2):
            start = time.monotonic()
            try:
                response = await provider.complete(system, user, max_tokens=max_tokens, json_mode=json_mode)
            except ProviderError as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                await self._log_usage(
                    db,
                    provider=provider.name,
                    model=provider.model,
                    purpose=purpose,
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(exc),
                )
                if exc.retryable and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                return None
            else:
                latency_ms = int((time.monotonic() - start) * 1000)
                await self._increment_daily_count(provider.name)
                await self._log_usage(
                    db,
                    provider=provider.name,
                    model=provider.model,
                    purpose=purpose,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    latency_ms=latency_ms,
                    success=True,
                )
                return response
        return None

    async def complete(
        self,
        db: AsyncSession,
        *,
        system: str,
        user: str,
        purpose: str,
        max_tokens: int = 200,
        json_mode: bool = False,
    ) -> str:
        providers = [self.primary, self.fallback]
        if await self._is_over_daily_limit(self.primary.name):
            providers = [self.fallback, self.primary]

        response: LLMResponse | None = None
        successful_provider: LLMProvider | None = None
        for provider in providers:
            response = await self._try_provider(
                db, provider, system=system, user=user, purpose=purpose, max_tokens=max_tokens, json_mode=json_mode
            )
            if response is not None:
                successful_provider = provider
                break

        if response is None or successful_provider is None:
            return CANNED_JSON_FALLBACK if json_mode else CANNED_TEXT_FALLBACK

        if not json_mode or _is_valid_json(response.text):
            return response.text

        retry_response = await self._try_provider(
            db,
            successful_provider,
            system=system + STRICT_JSON_INSTRUCTION,
            user=user,
            purpose=purpose,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        if retry_response is not None and _is_valid_json(retry_response.text):
            return retry_response.text

        return CANNED_JSON_FALLBACK


def get_default_router() -> LLMRouter:
    """The Groq-primary/Gemini-fallback router the conversation orchestrator
    (Phase 7) will use."""
    return LLMRouter(primary=GroqProvider(), fallback=GeminiProvider())
