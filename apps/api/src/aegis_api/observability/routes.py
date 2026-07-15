"""API observability routes — diagnostics and metric bridges."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import WORKSPACE_VERSION, AegisSettings
from aegis_contracts.observability import HealthResponseV1, HealthStatusV1, ReadyResponseV1
from aegis_contracts.versioning import HEALTH_RESPONSE_SCHEMA_VERSION, READY_RESPONSE_SCHEMA_VERSION
from aegis_event_streaming.metrics import GLOBAL_METRICS
from aegis_observability.health import (
    check_object_storage,
    check_postgres_bounded,
    check_redis_bounded,
    evaluate_readiness,
)
from aegis_observability.metrics import get_metrics, validate_metric_labels
from aegis_observability.setup import get_runtime
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from aegis_api.websocket.metrics import GLOBAL_GATEWAY_METRICS

public_router = APIRouter(tags=["observability"])
protected_router = APIRouter(tags=["observability"])


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def collect_dependency_statuses(settings: AegisSettings) -> list[Any]:
    timeout_ms = settings.AEGIS_HEALTH_PROBE_TIMEOUT_MS
    results = [
        await check_postgres_bounded(settings, timeout_ms=timeout_ms, required=True),
        await check_redis_bounded(
            settings,
            timeout_ms=timeout_ms,
            required=settings.AEGIS_READY_REQUIRE_REDIS,
        ),
        await check_object_storage(
            settings,
            timeout_ms=timeout_ms,
            required=settings.AEGIS_READY_REQUIRE_OBJECT_STORAGE,
        ),
    ]
    metrics = get_metrics()
    for result in results:
        try:
            labels = validate_metric_labels(
                {
                    "service": "api",
                    "operation": "dependency.probe",
                    "dependency": result.name,
                    "status": result.state.value,
                }
            )
            if result.latency_ms is not None:
                metrics.dependency_probe.record(result.latency_ms, labels)
        except Exception:  # noqa: BLE001
            runtime = get_runtime()
            if runtime is not None:
                runtime.record_exporter_failure()
    return results


def bridge_streaming_and_gateway_metrics() -> None:
    """Push in-memory domain metrics into OTel without duplicating business logic."""
    metrics = get_metrics()
    streaming = GLOBAL_METRICS.snapshot()
    gateway = GLOBAL_GATEWAY_METRICS.snapshot()
    try:
        service_labels = validate_metric_labels(
            {"service": "api", "operation": "metrics.bridge", "status": "ok"}
        )
        unpublished = int(streaming.get("outboxUnpublished") or 0)
        metrics.outbox_unpublished.add(unpublished, service_labels)
        lag = int(streaming.get("consumerLag") or 0)
        metrics.consumer_lag.add(lag, service_labels)
        age = streaming.get("outboxOldestAgeSeconds")
        if isinstance(age, (int, float)):
            metrics.outbox_delay.record(float(age), service_labels)
        publish_latency = streaming.get("publishLatencyMs")
        if isinstance(publish_latency, (int, float)):
            metrics.event_persist_latency.record(float(publish_latency), service_labels)
        ws_labels = validate_metric_labels(
            {"service": "api", "operation": "ws.bridge", "ws_event": "snapshot", "status": "ok"}
        )
        active_raw = gateway.get("activeConnections") or 0
        active = int(active_raw) if isinstance(active_raw, (int, float)) else 0
        metrics.ws_connections.add(active, ws_labels)
        delivery_lag = gateway.get("deliveryLagMs")
        if isinstance(delivery_lag, (int, float)):
            metrics.ws_delivery_lag.record(float(delivery_lag), ws_labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


@public_router.get("/live", response_model=None)
def live() -> dict[str, object]:
    """Explicit liveness alias — process is alive."""
    payload = HealthResponseV1.model_validate(
        {
            "schemaVersion": HEALTH_RESPONSE_SCHEMA_VERSION,
            "status": HealthStatusV1.OK.value,
            "service": "api",
            "version": WORKSPACE_VERSION,
            "checkedAt": _now(),
        }
    )
    return payload.model_dump(by_alias=True)


@protected_router.get("/diagnostics", response_model=None)
async def diagnostics(request: Request) -> dict[str, object]:
    """Protected dependency diagnostics — admin:manage only."""
    settings: AegisSettings = request.app.state.settings
    results = await collect_dependency_statuses(settings)
    bridge_streaming_and_gateway_metrics()
    status = evaluate_readiness(results)
    runtime = get_runtime()
    return {
        "schemaVersion": 1,
        "status": status.value,
        "service": "api",
        "environment": settings.AEGIS_ENV.value,
        "checkedAt": _now(),
        "dependencies": [r.to_status().model_dump(by_alias=True) for r in results],
        "streamingMetrics": GLOBAL_METRICS.snapshot(),
        "gatewayMetrics": GLOBAL_GATEWAY_METRICS.snapshot(),
        "telemetry": {
            "enabled": bool(runtime.enabled) if runtime else False,
            "exporterFailures": runtime.exporter_failures if runtime else 0,
            "serviceName": runtime.service_name if runtime else None,
        },
    }


@protected_router.get("/metrics", response_model=None)
async def metrics_text() -> PlainTextResponse:
    """Protected operational metrics snapshot (admin:manage)."""
    bridge_streaming_and_gateway_metrics()
    streaming = GLOBAL_METRICS.snapshot()
    gateway = GLOBAL_GATEWAY_METRICS.snapshot()
    lines = [
        "# AEGIS operational metrics snapshot (admin:manage)",
        f"aegis_outbox_unpublished {streaming.get('outboxUnpublished', 0)}",
        f"aegis_consumer_lag {streaming.get('consumerLag', 0)}",
        f"aegis_ws_active_connections {gateway.get('activeConnections', 0)}",
        f"aegis_ws_messages_sent {gateway.get('messagesSent', 0)}",
        f"aegis_ws_messages_received {gateway.get('messagesReceived', 0)}",
    ]
    runtime = get_runtime()
    if runtime is not None:
        lines.append(f"aegis_telemetry_exporter_failures {runtime.exporter_failures}")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")


async def build_ready_response(settings: AegisSettings) -> tuple[ReadyResponseV1, int]:
    results = await collect_dependency_statuses(settings)
    status = evaluate_readiness(results)
    payload = ReadyResponseV1.model_validate(
        {
            "schemaVersion": READY_RESPONSE_SCHEMA_VERSION,
            "status": status.value,
            "service": "api",
            "environment": settings.AEGIS_ENV.value,
            "dependencies": [r.to_status().model_dump(by_alias=True) for r in results],
            "checkedAt": _now(),
        }
    )
    code = 200 if status.value in {"ready", "degraded"} else 503
    return payload, code
