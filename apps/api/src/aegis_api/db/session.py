"""FastAPI database session lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import AegisSettings, load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: AegisSettings | None = None) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    resolved = settings or load_settings()
    _engine = create_engine(resolved)
    _session_maker = get_session_maker(resolved, engine=_engine)
    return _session_maker


async def shutdown_db(settings: AegisSettings | None = None) -> None:
    global _engine, _session_maker
    if _engine is not None:
        await dispose_engine(_engine)
    _engine = None
    _session_maker = None


def get_db_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        return init_db()
    return _session_maker


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        yield session
