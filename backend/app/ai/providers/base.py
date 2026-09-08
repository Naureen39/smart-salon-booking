"""Provider-agnostic LLM interface (docs plan §9.4). GroqProvider and
GeminiProvider both implement this; app/ai/llm_router.py depends only on it,
never on a specific provider's SDK/wire format.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """Raised by a provider on a failed call. `retryable` distinguishes
    transient issues (429 rate limit, 5xx) — which the router retries once
    then fails over on — from non-retryable ones (e.g. a 400 bad request,
    which retrying or switching providers won't fix)."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse: ...
