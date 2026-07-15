"""Bounded dependency health probes and readiness evaluation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from aegis_contracts.observability import (
    DependencyStateV1,
    DependencyStatusV1,
    ReadyStatusV1,
)
from aegis_contracts.versioning import DEPENDENCY_STATUS_SCHEMA_VERSION


@dataclass(slots=True)
class DependencyProbeResult:
    name: str
    state: DependencyStateV1
    required: bool
    latency_ms: float | None
    message: str | None = None

    def to_status(self) -> DependencyStatusV1:
        return DependencyStatusV1.model_validate(
            {
                "schemaVersion": DEPENDENCY_STATUS_SCHEMA_VERSION,
                "name": self.name,
                "state": self.state.value,
                "required": self.required,
                "latencyMs": self.latency_ms,
                "message": self.message,
                "checkedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )


async def _run_bounded(
    name: str,
    *,
    required: bool,
    timeout_ms: int,
    probe: Callable[[], Awaitable[bool]],
) -> DependencyProbeResult:
    started = time.perf_counter()
    try:
        ok = await asyncio.wait_for(probe(), timeout=timeout_ms / 1000.0)
        latency_ms = (time.perf_counter() - started) * 1000.0
        if ok:
            return DependencyProbeResult(
                name=name,
                state=DependencyStateV1.OK,
                required=required,
                latency_ms=latency_ms,
            )
        return DependencyProbeResult(
            name=name,
            state=DependencyStateV1.UNAVAILABLE,
            required=required,
            latency_ms=latency_ms,
            message=f"{name} probe returned false",
        )
    except TimeoutError:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return DependencyProbeResult(
            name=name,
            state=DependencyStateV1.UNAVAILABLE,
            required=required,
            latency_ms=latency_ms,
            message=f"{name} probe timed out after {timeout_ms}ms",
        )
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        return DependencyProbeResult(
            name=name,
            state=DependencyStateV1.FAILED,
            required=required,
            latency_ms=latency_ms,
            message=f"{name} probe error: {type(exc).__name__}",
        )


async def check_postgres_bounded(
    settings: Any,
    *,
    timeout_ms: int = 2000,
    required: bool = True,
) -> DependencyProbeResult:
    async def _probe() -> bool:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.postgres_async_dsn, pool_pre_ping=True)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                return bool(result.scalar_one() == 1)
        finally:
            await engine.dispose()

    return await _run_bounded("postgres", required=required, timeout_ms=timeout_ms, probe=_probe)


async def check_redis_bounded(
    settings: Any,
    *,
    timeout_ms: int = 2000,
    required: bool = True,
) -> DependencyProbeResult:
    async def _probe() -> bool:
        from redis.asyncio import Redis

        client = Redis.from_url(str(settings.REDIS_URL), socket_connect_timeout=timeout_ms / 1000.0)
        try:
            pong = await client.ping()
            return bool(pong)
        finally:
            await client.aclose()

    return await _run_bounded("redis", required=required, timeout_ms=timeout_ms, probe=_probe)


async def check_object_storage(
    settings: Any,
    *,
    timeout_ms: int = 2000,
    required: bool = True,
) -> DependencyProbeResult:
    async def _probe() -> bool:
        import httpx

        endpoint = str(settings.S3_ENDPOINT).rstrip("/")
        # Prefer MinIO/S3 live health when available; fall back to TCP-ish HEAD.
        health_url = f"{endpoint}/minio/health/live"
        async with httpx.AsyncClient(timeout=timeout_ms / 1000.0) as client:
            response = await client.get(health_url)
            if response.status_code < 500:
                return True
            # Generic S3 endpoints may not expose /minio/health/live.
            parsed = urlparse(endpoint)
            if not parsed.hostname:
                return False
            head = await client.head(endpoint)
            return head.status_code < 500

    return await _run_bounded(
        "object_storage",
        required=required,
        timeout_ms=timeout_ms,
        probe=_probe,
    )


def evaluate_readiness(results: list[DependencyProbeResult]) -> ReadyStatusV1:
    required_failed = [
        r
        for r in results
        if r.required and r.state in {DependencyStateV1.UNAVAILABLE, DependencyStateV1.FAILED}
    ]
    if required_failed:
        return ReadyStatusV1.NOT_READY
    degraded = [r for r in results if r.state == DependencyStateV1.DEGRADED]
    if degraded:
        return ReadyStatusV1.DEGRADED
    return ReadyStatusV1.READY
