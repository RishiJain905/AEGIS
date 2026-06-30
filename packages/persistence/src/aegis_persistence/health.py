"""PostgreSQL connectivity health checks."""

from __future__ import annotations

from aegis_contracts import AegisSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aegis_persistence.engine import create_engine


async def check_postgres(
    settings: AegisSettings,
    *,
    engine: AsyncEngine | None = None,
) -> bool:
    active_engine = engine or create_engine(settings)
    owns_engine = engine is None
    try:
        async with active_engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            value = result.scalar_one()
            return bool(value == 1)
    except Exception:
        return False
    finally:
        if owns_engine:
            await active_engine.dispose()


async def check_postgres_session(session: AsyncSession) -> bool:
    try:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar_one()
        return bool(value == 1)
    except Exception:
        return False
