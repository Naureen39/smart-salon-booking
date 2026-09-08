import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error

    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise credentials_error from exc

    if payload.get("type") != "access":
        raise credentials_error

    subject = payload.get("sub")
    if subject is None:
        raise credentials_error

    user = await db.get(User, uuid.UUID(subject))
    if user is None or not user.is_active:
        raise credentials_error

    return user


def require_role(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        # current_user was just loaded fresh from the DB above, so this checks the
        # authoritative row rather than trusting the JWT's role claim.
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return _checker
