from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Lazily creates the Redis client on first use, within whichever event loop
    is running at that point — safer than a module-level singleton created at
    import time, since asyncio connections are bound to the loop that created
    them (matters for tests, which run each test on its own loop)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def reset_redis_client() -> None:
    """Test-only helper: closes and drops the cached client so the next
    get_redis_client() call creates a fresh one bound to the current loop."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
