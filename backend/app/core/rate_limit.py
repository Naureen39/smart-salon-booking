"""Redis-backed sliding-window rate limiting (docs plan §7.5/§8) — protects
auth endpoints from brute force and chat/voice endpoints from burning
through the free LLM/STT quotas.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
