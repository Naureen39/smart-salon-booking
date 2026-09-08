import httpx

from app.ai.providers.base import LLMResponse, ProviderError
from app.core.config import get_settings

settings = get_settings()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    """Fallback provider (docs plan §9.4) — a second free-tier budget to burst
    into once Groq's daily/rate cap is hit.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model_primary
        self._transport = transport

    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> LLMResponse:
        url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={self.api_key}"
        generation_config: dict[str, object] = {"maxOutputTokens": max_tokens}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        }

        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as http_client:
            try:
                response = await http_client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise ProviderError(f"Gemini request failed: {exc}", retryable=True) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderError(f"Gemini returned {response.status_code}", retryable=True)
        if response.status_code >= 400:
            raise ProviderError(f"Gemini returned {response.status_code}: {response.text}", retryable=False)

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
        )
