from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, sourced from environment variables / .env.

    Field names are matched case-insensitively against env vars of the same
    name (e.g. `database_url` <- `DATABASE_URL`) by pydantic-settings.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    environment: str = "development"
    secret_key: str = "dev-secret-key-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql+asyncpg://glowdesk:glowdesk@localhost:5432/glowdesk"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM providers (free tiers)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str = ""
    gemini_model_primary: str = "gemini-2.5-flash"
    gemini_model_lite: str = "gemini-2.5-flash-lite"
    # Free-tier daily request ceilings the router proactively switches away from
    # before hitting a hard 429 (docs plan §9.4). Groq's published free tier is
    # 1,000 RPD; Gemini's isn't stated as precisely in the plan, so 1500 is a
    # conservative documented default — adjust here if providers change limits.
    groq_daily_request_limit: int = 1000
    gemini_daily_request_limit: int = 1500

    # Voice
    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8"
    tts_engine: str = "pyttsx3"
    # Default is the zero-setup offline fallback (see app/ai/tts.py) rather than
    # the plan's named "openvoice_v2" — OpenVoice V2 has no clean pip wheel and
    # needs a manually-downloaded checkpoint, so it can't be the default until
    # that's provisioned. Set TTS_ENGINE=openvoice_v2 once it is.
    tts_reference_voice_path: str = "/app/assets/brand_voice_sample.wav"
    tts_checkpoint_dir: str = "/app/assets/openvoice_v2_checkpoint"

    # RAG
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Empirically calibrated against BAAI/bge-small-en-v1.5's real cosine-similarity
    # distribution: genuine paraphrase matches scored 0.67-0.81, unrelated queries
    # scored 0.42-0.56 (see the Phase 5 verification notes). 0.65 sits cleanly
    # between the two clusters — the plan's suggested 0.82 would reject nearly
    # every legitimate FAQ match for this model.
    rag_similarity_threshold: float = 0.65

    # Email (reminders)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # Rate limiting
    rate_limit_chat_per_minute: int = 10
    rate_limit_voice_per_minute: int = 5

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
