"""Safe instrumentation helpers for domain operations (fail-open)."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from aegis_observability.context import merge_context
from aegis_observability.logging import get_logger
from aegis_observability.metrics import get_metrics, validate_metric_labels
from aegis_observability.setup import get_runtime


@contextmanager
def traced_operation(
    *,
    service: str,
    operation: str,
    span_name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Start a span + bind context. Never raises into the caller for telemetry failures."""
    started = time.perf_counter()
    state: dict[str, Any] = {"status": "ok", "error_kind": None}
    span = None
    try:
        merge_context(service=service, operation=operation)
        safe_attrs = {
            k: v
            for k, v in (attributes or {}).items()
            if k
            not in {
                "prompt",
                "content",
                "messages",
                "authorization",
                "cookie",
                "token",
                "password",
            }
            and not isinstance(v, (dict, list))
        }
        runtime = get_runtime()
        if runtime is not None and runtime.tracer_provider is not None:
            from opentelemetry import trace

            tracer = trace.get_tracer(service)
            span = tracer.start_span(span_name or operation)
            for key, value in safe_attrs.items():
                if value is not None:
                    span.set_attribute(f"aegis.{key}", str(value)[:128])
        yield state
        if span is not None and state["status"] != "ok":
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR, state.get("error_kind") or "error"))
    except Exception:
        state["status"] = "error"
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        state["duration_ms"] = duration_ms
        try:
            merge_context(duration_ms=duration_ms)
            log_attrs = {
                k: v
                for k, v in (attributes or {}).items()
                if isinstance(v, (str, int, float, bool))
            }
            get_logger(operation, service=service).info(
                f"{operation} completed",
                operation=operation,
                outcome="failure" if state["status"] != "ok" else "success",
                duration_ms=duration_ms,
                error_kind=state.get("error_kind"),
                **log_attrs,
            )
        except Exception:  # noqa: BLE001
            pass
        if span is not None:
            with contextlib.suppress(Exception):
                span.end()


def record_provider_call(
    *,
    provider: str,
    model_alias: str,
    duration_ms: float,
    status: str,
    retries: int = 0,
    tokens: int | None = None,
    cost: float | None = None,
) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {
                "service": "model-provider",
                "operation": "provider.generate",
                "provider": provider[:64],
                "model_alias": model_alias[:64],
                "status": status[:64],
            }
        )
        metrics.provider_calls.add(1, labels)
        metrics.provider_latency.record(duration_ms, labels)
        if retries:
            metrics.provider_retries.add(retries, labels)
        if tokens is not None:
            metrics.provider_tokens.add(tokens, labels)
        if cost is not None:
            metrics.provider_cost.add(cost, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


def record_agent_task(
    *,
    agent_name: str,
    duration_ms: float,
    status: str,
    tool_failure: bool = False,
    cost: float | None = None,
) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {
                "service": "agents",
                "operation": "agent.task",
                "agent_name": agent_name[:64].lower(),
                "status": status[:64],
            }
        )
        metrics.agent_latency.record(duration_ms, labels)
        if tool_failure:
            metrics.agent_tool_failures.add(1, labels)
        if cost is not None:
            metrics.agent_cost.add(cost, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


def record_simulation_events(
    *,
    count: int,
    duration_ms: float | None = None,
    status: str = "ok",
) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {
                "service": "simulator",
                "operation": "simulation.step",
                "status": status,
            }
        )
        metrics.simulation_events.add(count, labels)
        if duration_ms is not None:
            metrics.simulation_duration.record(duration_ms, labels)
        if status in {"completed", "failed"}:
            metrics.simulation_completions.add(1, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


def record_replay(*, duration_ms: float, status: str, event_count: int = 0) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {"service": "replay", "operation": "replay.reconstruct", "status": status}
        )
        metrics.replay_duration.record(duration_ms, labels)
        if event_count:
            metrics.replay_events.add(event_count, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


def record_scoring(*, duration_ms: float, status: str) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {"service": "scoring", "operation": "scoring.score_run", "status": status}
        )
        metrics.scoring_duration.record(duration_ms, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()


def record_approval_wait(*, duration_ms: float, status: str) -> None:
    try:
        metrics = get_metrics()
        labels = validate_metric_labels(
            {"service": "api", "operation": "approval.decide", "status": status}
        )
        metrics.approval_wait.record(duration_ms, labels)
    except Exception:  # noqa: BLE001
        runtime = get_runtime()
        if runtime is not None:
            runtime.record_exporter_failure()
