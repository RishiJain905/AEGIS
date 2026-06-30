"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import AegisSettings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(settings: AegisSettings) -> AsyncEngine:
    return create_async_engine(
        settings.postgres_async_dsn,
        pool_pre_ping=True,
        echo=False,
    )


def get_session_maker(
    settings: AegisSettings,
    *,
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    active_engine = engine or create_engine(settings)
    return async_sessionmaker(
        active_engine,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )


@asynccontextmanager
async def session_scope(settings: AegisSettings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def dispose_engine(engine: AsyncEngine) -> None:
    await engine.dispose()
