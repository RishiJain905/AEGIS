"""Shared fixtures for streaming integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from aegis_contracts import AegisSettings
from aegis_event_streaming.redis_client import create_redis_client
from redis.asyncio import Redis


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


@pytest.fixture
async def streaming_ready(
    redis_client: Redis,
    migrated_database: None,
) -> Redis:
    _ = migrated_database
    return redis_client
