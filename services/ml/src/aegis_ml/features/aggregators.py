"""Per-window telemetry aggregators."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from aegis_contracts.events import DomainEventEnvelopeV1

from aegis_ml.features.schema_registry import MISSING_SENTINEL, NET_PROTOCOL_VALUES


@dataclass
class WindowAccumulator:
    entity_id: str
    window_start_epoch: int
    window_start: datetime
    window_end: datetime
    sequence_start: int | None = None
    sequence_end: int | None = None
    sim_time_start: datetime | None = None
    sim_time_end: datetime | None = None
    source_event_ids: list[str] = field(default_factory=list)
    auth_events: int = 0
    auth_failed: int = 0
    api_requests: int = 0
    api_errors: int = 0
    db_queries: int = 0
    db_anomalous: int = 0
    net_connections: int = 0
    net_bytes_total: int = 0
    net_protocol_bytes: dict[str, int] = field(default_factory=dict)
    proc_events: int = 0
    proc_suspicious: int = 0
    deploy_count: int = 0
    deploy_failed: int = 0
    health_checks: int = 0
    health_unhealthy: int = 0
    ai_inferences: int = 0
    ai_anomalous: int = 0
    telemetry_event_count: int = 0

    def record_bounds(self, event: DomainEventEnvelopeV1) -> None:
        if self.sequence_start is None:
            self.sequence_start = event.sequence
            self.sim_time_start = event.sim_time
        self.sequence_end = event.sequence
        self.sim_time_end = event.sim_time
        self.source_event_ids.append(event.event_id)

    def ingest(self, event: DomainEventEnvelopeV1) -> None:
        self.record_bounds(event)
        self.telemetry_event_count += 1
        event_type = event.type
        payload = event.payload

        if event_type in {"telemetry.authentication.failed", "telemetry.authentication.succeeded"}:
            self.auth_events += 1
            if event_type.endswith(".failed"):
                self.auth_failed += 1
            return

        if event_type == "telemetry.api.request":
            self.api_requests += 1
            if int(payload.get("statusCode", 200)) >= 400:
                self.api_errors += 1
            return

        if event_type == "telemetry.database.query":
            self.db_queries += int(payload.get("queryCount", 0))
            if bool(payload.get("anomalous", False)):
                self.db_anomalous += 1
            return

        if event_type == "telemetry.network.connection":
            self.net_connections += 1
            protocol = str(payload.get("protocol", "__MISSING__"))
            if protocol not in NET_PROTOCOL_VALUES:
                protocol = "__MISSING__"
            bytes_count = int(payload.get("bytes", 0))
            self.net_bytes_total += bytes_count
            self.net_protocol_bytes[protocol] = (
                self.net_protocol_bytes.get(protocol, 0) + bytes_count
            )
            return

        if event_type == "telemetry.process.activity":
            self.proc_events += int(payload.get("eventCount", 0))
            if bool(payload.get("suspicious", False)):
                self.proc_suspicious += 1
            return

        if event_type == "telemetry.deployment.event":
            self.deploy_count += int(payload.get("deploymentCount", 0))
            if bool(payload.get("failed", False)):
                self.deploy_failed += 1
            return

        if event_type == "telemetry.health.check":
            self.health_checks += 1
            if not bool(payload.get("healthy", True)):
                self.health_unhealthy += 1
            return

        if event_type == "telemetry.ai.inference":
            self.ai_inferences += int(payload.get("inferenceCount", 0))
            if bool(payload.get("anomalous", False)):
                self.ai_anomalous += 1


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return MISSING_SENTINEL
    return numerator / denominator


def _dominant_protocol(protocol_bytes: dict[str, int]) -> str:
    if not protocol_bytes:
        return "__MISSING__"
    ranked = sorted(protocol_bytes.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _one_hot_protocol(protocol: str) -> tuple[float, float, float]:
    return (
        1.0 if protocol == "tcp" else 0.0,
        1.0 if protocol == "udp" else 0.0,
        1.0 if protocol == "__MISSING__" else 0.0,
    )


def accumulator_to_values(accumulator: WindowAccumulator) -> list[float]:
    dominant = _dominant_protocol(accumulator.net_protocol_bytes)
    tcp, udp, missing = _one_hot_protocol(dominant)
    net_mean = (
        accumulator.net_bytes_total / accumulator.net_connections
        if accumulator.net_connections > 0
        else MISSING_SENTINEL
    )
    return [
        float(accumulator.auth_events),
        float(accumulator.auth_failed),
        _safe_rate(float(accumulator.auth_failed), float(accumulator.auth_events)),
        float(accumulator.api_requests),
        float(accumulator.api_errors),
        _safe_rate(float(accumulator.api_errors), float(accumulator.api_requests)),
        float(accumulator.db_queries),
        float(accumulator.db_anomalous),
        _safe_rate(float(accumulator.db_anomalous), float(accumulator.db_queries)),
        float(accumulator.net_connections),
        float(accumulator.net_bytes_total),
        float(net_mean),
        tcp,
        udp,
        missing,
        float(accumulator.proc_events),
        float(accumulator.proc_suspicious),
        _safe_rate(float(accumulator.proc_suspicious), float(accumulator.proc_events)),
        float(accumulator.deploy_count),
        float(accumulator.deploy_failed),
        _safe_rate(float(accumulator.deploy_failed), float(accumulator.deploy_count)),
        float(accumulator.health_checks),
        float(accumulator.health_unhealthy),
        _safe_rate(float(accumulator.health_unhealthy), float(accumulator.health_checks)),
        float(accumulator.ai_inferences),
        float(accumulator.ai_anomalous),
        _safe_rate(float(accumulator.ai_anomalous), float(accumulator.ai_inferences)),
    ]
