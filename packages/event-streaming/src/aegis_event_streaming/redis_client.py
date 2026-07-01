"""Async Redis client factory."""

from __future__ import annotations

from aegis_contracts import AegisSettings
from redis.asyncio import Redis


def create_redis_client(settings: AegisSettings) -> Redis:
    return Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
