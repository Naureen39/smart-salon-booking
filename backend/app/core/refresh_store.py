import hashlib

from app.core.config import get_settings
from app.core.redis import get_redis_client

settings = get_settings()


def _key(jti: str) -> str:
    return f"refresh_token:{jti}"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def store_refresh_token(jti: str, token: str) -> None:
    ttl_seconds = settings.refresh_token_expire_days * 24 * 60 * 60
    await get_redis_client().set(_key(jti), _hash(token), ex=ttl_seconds)


async def is_refresh_token_valid(jti: str, token: str) -> bool:
    """Checks the token against its Redis allowlist entry — absent or mismatched means
    already used (rotated away), revoked (logout), or expired."""
    stored_hash = await get_redis_client().get(_key(jti))
    if stored_hash is None:
        return False
    return stored_hash == _hash(token)


async def revoke_refresh_token(jti: str) -> None:
    await get_redis_client().delete(_key(jti))
