import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.email import send_email
from app.core.redis import get_redis_client
from app.core.refresh_store import is_refresh_token_valid, revoke_refresh_token, store_refresh_token
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AccessTokenResponse, LoginRequest, SignupRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
EMAIL_VERIFY_TTL_SECONDS = 60 * 60 * 24


async def _issue_tokens(response: Response, user: User) -> AccessTokenResponse:
    access_token = create_access_token(user.id, user.role)
    refresh_token, jti = create_refresh_token(user.id, user.role)
    await store_refresh_token(jti, refresh_token)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.environment != "development",
        samesite="strict",
    )
    return AccessTokenResponse(access_token=access_token)


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="client",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    verify_token = str(uuid.uuid4())
    await get_redis_client().set(f"email_verify:{verify_token}", str(user.id), ex=EMAIL_VERIFY_TTL_SECONDS)
    send_email(
        user.email,
        "Verify your GlowDesk account",
        f"Welcome to GlowDesk! Verify your email using this token: {verify_token}",
    )

    return user


@router.post("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token"
    )

    user_id = await get_redis_client().get(f"email_verify:{token}")
    if user_id is None:
        raise invalid_token

    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        raise invalid_token

    user.is_verified = True
    await db.commit()
    await get_redis_client().delete(f"email_verify:{token}")

    return {"detail": "Email verified"}


@router.post("/login", response_model=AccessTokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    invalid_credentials = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return await _issue_tokens(response, user)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    invalid_token = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is None:
        raise invalid_token

    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise invalid_token from exc

    if payload.get("type") != "refresh":
        raise invalid_token

    jti = payload.get("jti")
    if jti is None or not await is_refresh_token_valid(jti, token):
        raise invalid_token

    # Rotate: the used token is invalidated before a new pair is issued, so a
    # replayed (stolen) refresh token stops working the moment the legitimate
    # client refreshes.
    await revoke_refresh_token(jti)

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise invalid_token

    return await _issue_tokens(response, user)


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is not None:
        try:
            payload = decode_token(token)
        except JWTError:
            payload = None
        if payload is not None:
            jti = payload.get("jti")
            if jti is not None:
                await revoke_refresh_token(jti)

    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
