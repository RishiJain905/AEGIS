"""Shared fixtures for integration tests against real PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from aegis_contracts import AegisSettings, load_settings
from aegis_event_streaming.redis_client import create_redis_client
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _postgres_available(settings: AegisSettings) -> bool:
    try:
        import psycopg

        conn = psycopg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            dbname=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def settings() -> AegisSettings:
    if not os.path.exists(".env"):
        pytest.skip("Missing .env — copy from .env.example")
    return load_settings()


@pytest.fixture(scope="session")
def postgres_available(settings: AegisSettings) -> None:
    if not _postgres_available(settings):
        pytest.skip("PostgreSQL is not available — run docker compose up -d postgres")


@pytest.fixture(scope="session")
def migrated_database(settings: AegisSettings, postgres_available: None) -> Iterator[None]:
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield


@pytest.fixture
async def db_engine(settings: AegisSettings, migrated_database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(settings)
    yield engine
    await dispose_engine(engine)


@pytest.fixture
async def session_maker(
    settings: AegisSettings,
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return get_session_maker(settings, engine=db_engine)


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_maker() as session:
        for table in (
            "dead_letters",
            "consumer_cursors",
            "consumer_receipts",
            "simulation_checkpoints",
            "outbox",
            "domain_events",
            "idempotency_records",
            "graph_snapshots",
            "model_scores",
            "model_manifests",
            "executed_actions",
            "approvals",
            "action_proposals",
            "agent_sessions",
            "hypotheses",
            "evidence",
            "incidents",
            "alerts",
            "relationship_instances",
            "asset_instances",
            "runs",
            "scenario_versions",
            "scenarios",
            "stored_objects",
            "tools",
        ):
            await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session
        await session.rollback()


@pytest.fixture
async def unit_of_work(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> AsyncIterator[PostgresUnitOfWork]:
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        yield uow


def _redis_available(settings: AegisSettings) -> bool:
    try:
        import redis as redis_sync

        client = redis_sync.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def redis_available(settings: AegisSettings) -> None:
    if not _redis_available(settings):
        pytest.skip("Redis is not available — run docker compose up -d redis")


@pytest.fixture
async def redis_client(settings: AegisSettings, redis_available: None) -> AsyncIterator[Redis]:
    client = create_redis_client(settings)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
