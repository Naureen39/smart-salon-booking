import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    role: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    jti: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(str(user_id), role, "access", timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: uuid.UUID, role: str) -> tuple[str, str]:
    """Returns (token, jti) — the jti is the allowlist key the caller stores in Redis."""
    jti = str(uuid.uuid4())
    token = _create_token(str(user_id), role, "refresh", timedelta(days=settings.refresh_token_expire_days), jti=jti)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """Raises jose.JWTError (or a subclass, e.g. ExpiredSignatureError) on an invalid/expired token."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
