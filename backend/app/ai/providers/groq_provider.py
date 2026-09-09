import httpx

from app.ai.providers.base import LLMResponse, ProviderError
from app.core.config import get_settings

settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:
    """Primary provider (docs plan §9.4) — fastest, generous free daily budget.
    Uses Groq's OpenAI-compatible chat completions endpoint.
    """

    name = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model
        self._transport = transport

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            # The default model (gpt-oss-20b) is a reasoning model: it spends
            # part of max_tokens on a hidden reasoning trace before any
            # visible content, and a numeric instruction like "under 40
            # words" was observed (in manual end-to-end testing) to push it
            # into literally counting words in that trace, consuming the
            # entire budget and returning blank content with
            # finish_reason="length". "low" cut reasoning from ~130 tokens
            # to single digits for this project's short confirmation/FAQ
            # prompts with no loss of answer quality, harmless to send even
            # if a future non-reasoning model on Groq ignores the field.
            "reasoning_effort": "low",
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as http_client:
            try:
                response = await http_client.post(
                    GROQ_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            except httpx.RequestError as exc:
                raise ProviderError(f"Groq request failed: {exc}", retryable=True) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderError(f"Groq returned {response.status_code}", retryable=True)
        if response.status_code >= 400:
            raise ProviderError(f"Groq returned {response.status_code}: {response.text}", retryable=False)

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )
