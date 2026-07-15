"""Bounded-cardinality OpenTelemetry metrics for AEGIS services."""

from __future__ import annotations

from threading import Lock
from typing import Any

from aegis_contracts.observability import ALLOWED_METRIC_LABELS, FORBIDDEN_METRIC_LABELS

_METRICS_LOCK = Lock()
_METRICS: AegisMetrics | None = None


class MetricLabelError(ValueError):
    """Raised when metric labels violate the cardinality policy."""


def validate_metric_labels(labels: dict[str, str]) -> dict[str, str]:
    for key, value in labels.items():
        if key in FORBIDDEN_METRIC_LABELS:
            raise MetricLabelError(f"Forbidden high-cardinality metric label: {key}")
        if key not in ALLOWED_METRIC_LABELS:
            raise MetricLabelError(f"Metric label not in allowlist: {key}")
        if len(value) > 64:
            raise MetricLabelError(f"Metric label value too long for {key}")
    return labels


class _NoopInstrument:
    def add(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def record(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class AegisMetrics:
    """Registers the architecture §19 minimum operational metric set."""

    def __init__(self, meter: Any | None = None, *, service: str = "aegis") -> None:
        self.service = service
        self._meter = meter
        self._exporter_failures = 0
        self._lock = Lock()
        if meter is None:
            self.api_request_duration = _NoopInstrument()
            self.api_request_errors = _NoopInstrument()
            self.api_requests = _NoopInstrument()
            self.ws_connections = _NoopInstrument()
            self.ws_messages = _NoopInstrument()
            self.ws_delivery_lag = _NoopInstrument()
            self.outbox_delay = _NoopInstrument()
            self.outbox_unpublished = _NoopInstrument()
            self.consumer_lag = _NoopInstrument()
            self.event_persist_latency = _NoopInstrument()
            self.event_persist_failures = _NoopInstrument()
            self.sequence_gaps = _NoopInstrument()
            self.worker_queue_depth = _NoopInstrument()
            self.simulation_events = _NoopInstrument()
            self.simulation_duration = _NoopInstrument()
            self.simulation_completions = _NoopInstrument()
            self.ml_inference_latency = _NoopInstrument()
            self.provider_latency = _NoopInstrument()
            self.provider_calls = _NoopInstrument()
            self.provider_retries = _NoopInstrument()
            self.provider_tokens = _NoopInstrument()
            self.provider_cost = _NoopInstrument()
            self.agent_latency = _NoopInstrument()
            self.agent_tool_failures = _NoopInstrument()
            self.agent_cost = _NoopInstrument()
            self.snapshot_duration = _NoopInstrument()
            self.replay_duration = _NoopInstrument()
            self.replay_events = _NoopInstrument()
            self.scoring_duration = _NoopInstrument()
            self.approval_wait = _NoopInstrument()
            self.dependency_probe = _NoopInstrument()
            self.telemetry_exporter_failures = _NoopInstrument()
            return

        self.api_request_duration = meter.create_histogram(
            "aegis.api.request.duration",
            unit="ms",
            description="HTTP API request duration",
        )
        self.api_request_errors = meter.create_counter(
            "aegis.api.request.errors",
            unit="1",
            description="HTTP API request errors",
        )
        self.api_requests = meter.create_counter(
            "aegis.api.request.count",
            unit="1",
            description="HTTP API request count",
        )
        self.ws_connections = meter.create_up_down_counter(
            "aegis.ws.connections",
            unit="1",
            description="Active WebSocket connections",
        )
        self.ws_messages = meter.create_counter(
            "aegis.ws.messages",
            unit="1",
            description="WebSocket messages",
        )
        self.ws_delivery_lag = meter.create_histogram(
            "aegis.ws.delivery_lag",
            unit="ms",
            description="WebSocket delivery lag",
        )
        self.outbox_delay = meter.create_histogram(
            "aegis.outbox.delay",
            unit="s",
            description="Outbox publish delay",
        )
        self.outbox_unpublished = meter.create_up_down_counter(
            "aegis.outbox.unpublished",
            unit="1",
            description="Unpublished outbox rows",
        )
        self.consumer_lag = meter.create_up_down_counter(
            "aegis.stream.consumer_lag",
            unit="1",
            description="Redis stream consumer lag",
        )
        self.event_persist_latency = meter.create_histogram(
            "aegis.event.persist.duration",
            unit="ms",
            description="Event persistence write latency",
        )
        self.event_persist_failures = meter.create_counter(
            "aegis.event.persist.failures",
            unit="1",
            description="Event persistence failures",
        )
        self.sequence_gaps = meter.create_counter(
            "aegis.event.sequence_gaps",
            unit="1",
            description="Detected event sequence gaps",
        )
        self.worker_queue_depth = meter.create_up_down_counter(
            "aegis.worker.queue_depth",
            unit="1",
            description="Worker queue depth",
        )
        self.simulation_events = meter.create_counter(
            "aegis.simulation.events",
            unit="1",
            description="Simulation events emitted",
        )
        self.simulation_duration = meter.create_histogram(
            "aegis.simulation.duration",
            unit="ms",
            description="Simulation run duration",
        )
        self.simulation_completions = meter.create_counter(
            "aegis.simulation.completions",
            unit="1",
            description="Simulation completions and failures",
        )
        self.ml_inference_latency = meter.create_histogram(
            "aegis.ml.inference.duration",
            unit="ms",
            description="ML inference latency",
        )
        self.provider_latency = meter.create_histogram(
            "aegis.provider.request.duration",
            unit="ms",
            description="Model provider call latency",
        )
        self.provider_calls = meter.create_counter(
            "aegis.provider.request.count",
            unit="1",
            description="Model provider calls",
        )
        self.provider_retries = meter.create_counter(
            "aegis.provider.request.retries",
            unit="1",
            description="Model provider retries",
        )
        self.provider_tokens = meter.create_counter(
            "aegis.provider.tokens",
            unit="1",
            description="Model provider token usage",
        )
        self.provider_cost = meter.create_counter(
            "aegis.provider.cost",
            unit="1",
            description="Model provider cost units",
        )
        self.agent_latency = meter.create_histogram(
            "aegis.agent.task.duration",
            unit="ms",
            description="Agent task duration",
        )
        self.agent_tool_failures = meter.create_counter(
            "aegis.agent.tool.failures",
            unit="1",
            description="Agent tool invocation failures",
        )
        self.agent_cost = meter.create_counter(
            "aegis.agent.cost",
            unit="1",
            description="Agent cost units",
        )
        self.snapshot_duration = meter.create_histogram(
            "aegis.snapshot.duration",
            unit="ms",
            description="Snapshot generation duration",
        )
        self.replay_duration = meter.create_histogram(
            "aegis.replay.duration",
            unit="ms",
            description="Replay reconstruction duration",
        )
        self.replay_events = meter.create_counter(
            "aegis.replay.events",
            unit="1",
            description="Replay event counts",
        )
        self.scoring_duration = meter.create_histogram(
            "aegis.scoring.duration",
            unit="ms",
            description="Scoring operation duration",
        )
        self.approval_wait = meter.create_histogram(
            "aegis.approval.wait",
            unit="ms",
            description="Approval wait time",
        )
        self.dependency_probe = meter.create_histogram(
            "aegis.dependency.probe.duration",
            unit="ms",
            description="Dependency health probe duration",
        )
        self.telemetry_exporter_failures = meter.create_counter(
            "aegis.telemetry.exporter.failures",
            unit="1",
            description="Telemetry exporter failures",
        )

    def record_api_request(
        self,
        *,
        duration_ms: float,
        status: str,
        method: str,
        route_group: str,
        error: bool = False,
    ) -> None:
        labels = validate_metric_labels(
            {
                "service": self.service,
                "operation": "http.request",
                "status": status,
                "method": method,
                "route_group": route_group,
            }
        )
        self.api_requests.add(1, labels)
        self.api_request_duration.record(duration_ms, labels)
        if error:
            self.api_request_errors.add(1, labels)

    def record_exporter_failure(self) -> None:
        with self._lock:
            self._exporter_failures += 1
        try:
            self.telemetry_exporter_failures.add(
                1,
                validate_metric_labels(
                    {"service": self.service, "operation": "otel.export", "status": "failure"}
                ),
            )
        except Exception:
            # Never let telemetry failure propagate.
            return None

    @property
    def exporter_failure_count(self) -> int:
        with self._lock:
            return self._exporter_failures


def get_metrics() -> AegisMetrics:
    global _METRICS
    with _METRICS_LOCK:
        if _METRICS is None:
            _METRICS = AegisMetrics(None, service="aegis")
        return _METRICS


def set_metrics(metrics: AegisMetrics) -> None:
    global _METRICS
    with _METRICS_LOCK:
        _METRICS = metrics


def reset_metrics_for_tests() -> None:
    global _METRICS
    with _METRICS_LOCK:
        _METRICS = None
