import asyncio
from collections.abc import AsyncGenerator
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.redis import get_redis_client, reset_redis_client
from app.core.security import hash_password
from app.db import models  # noqa: F401  registers all models on Base.metadata
from app.db.base import Base
from app.db.models.location import Location
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.db.session import get_db
from app.main import app

settings = get_settings()

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _working_hours_for(target_date: date) -> dict:
    return {WEEKDAY_KEYS[target_date.weekday()]: ["09:00-17:00"]}


def _setup_schema() -> None:
    """Runs once per session, on its own throwaway loop (via asyncio.run), fully
    decoupled from pytest-asyncio's per-test loops — see the `db_engine` fixture
    below for why each test gets its own engine bound to its own loop instead of
    sharing one across tests."""

    async def _run() -> None:
        setup_engine = create_async_engine(settings.database_url)
        async with setup_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await setup_engine.dispose()

    asyncio.run(_run())


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    _setup_schema()


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """A fresh engine per test, bound to that test's own event loop. asyncpg
    connections are loop-bound, and pytest-asyncio gives each test function its
    own loop by default — a shared/global engine would end up with pooled
    connections attached to a stale loop from an earlier test."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _override_get_db(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
async def _clean_state(db_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await get_redis_client().flushdb()
    # Drops the cached client so the next test lazily creates a fresh one bound
    # to its own event loop (see get_redis_client's docstring / db_engine above).
    await reset_redis_client()


@pytest.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def target_date() -> date:
    # A week out, so it's always in the future no matter when the suite runs.
    return date.today() + timedelta(days=7)


@pytest.fixture
async def location(db_session: AsyncSession) -> Location:
    loc = Location(name="Main Branch", timezone="UTC")
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)
    return loc


@pytest.fixture
async def service(db_session: AsyncSession) -> Service:
    svc = Service(name="Haircut", duration_minutes=30, price_cents=3000)
    db_session.add(svc)
    await db_session.commit()
    await db_session.refresh(svc)
    return svc


@pytest.fixture
async def staff(db_session: AsyncSession, location: Location, target_date: date) -> StaffProfile:
    profile = StaffProfile(location_id=location.id, title="Stylist", working_hours=_working_hours_for(target_date))
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest.fixture
async def client_user(db_session: AsyncSession) -> User:
    user = User(
        email="bookingclient@example.com",
        hashed_password=hash_password("password123"),
        full_name="Booking Client",
        role="client",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass123"),
        full_name="Admin User",
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
