"""Phase 31 observability contracts — telemetry context, logs, health, metrics policy."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AgentSessionId,
    CorrelationId,
    IncidentId,
    RunId,
    Sequence,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    DEPENDENCY_STATUS_SCHEMA_VERSION,
    HEALTH_RESPONSE_SCHEMA_VERSION,
    METRIC_LABEL_POLICY_SCHEMA_VERSION,
    READY_RESPONSE_SCHEMA_VERSION,
    STRUCTURED_LOG_RECORD_SCHEMA_VERSION,
    TELEMETRY_CONTEXT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class HealthStatusV1(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class ReadyStatusV1(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    DEGRADED = "degraded"


class DependencyStateV1(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SKIPPED = "skipped"


class LogOutcomeV1(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ActorKindV1(StrEnum):
    USER = "user"
    SERVICE = "service"
    SYSTEM = "system"
    AGENT = "agent"
    ANONYMOUS = "anonymous"


class MetricTypeV1(StrEnum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    UP_DOWN_COUNTER = "up_down_counter"


# Bounded-cardinality metric labels. Entity IDs belong in traces/logs only.
ALLOWED_METRIC_LABELS: frozenset[str] = frozenset(
    {
        "service",
        "operation",
        "status",
        "outcome",
        "provider",
        "model_alias",
        "agent_name",
        "dependency",
        "method",
        "route_group",
        "error_kind",
        "ws_event",
    }
)

FORBIDDEN_METRIC_LABELS: frozenset[str] = frozenset(
    {
        "user_id",
        "userId",
        "event_id",
        "eventId",
        "request_id",
        "requestId",
        "trace_id",
        "traceId",
        "run_id",
        "runId",
        "incident_id",
        "incidentId",
        "prompt",
        "url",
        "error_message",
        "errorMessage",
        "session_id",
        "sessionId",
        "actor_id",
        "actorId",
    }
)


class TelemetryContextV1(BaseModel):
    """Correlation context propagated across HTTP, WS, workers, and agents."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    trace_id: TraceId = Field(alias="traceId")
    span_id: str | None = Field(default=None, alias="spanId", max_length=32)
    correlation_id: CorrelationId | None = Field(default=None, alias="correlationId")
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)
    run_id: RunId | None = Field(default=None, alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    agent_session_id: AgentSessionId | None = Field(default=None, alias="agentSessionId")
    event_sequence: Sequence | None = Field(default=None, alias="eventSequence")
    service: str = Field(min_length=1, max_length=64)
    operation: str = Field(min_length=1, max_length=128)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)
    actor_kind: ActorKindV1 | None = Field(default=None, alias="actorKind")
    actor_role: str | None = Field(default=None, alias="actorRole", max_length=64)
    outcome: LogOutcomeV1 | None = None
    duration_ms: float | None = Field(default=None, alias="durationMs", ge=0)
    baggage: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> TelemetryContextV1:
        assert_supported_schema_version("telemetry_context", self.schema_version)
        if self.schema_version != TELEMETRY_CONTEXT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported telemetry_context schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class StructuredLogRecordV1(BaseModel):
    """Machine-readable structured log record for production logging."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    timestamp: UtcTimestamp
    level: str = Field(min_length=1, max_length=16)
    message: str = Field(min_length=1, max_length=4096)
    trace_id: TraceId | None = Field(default=None, alias="traceId")
    span_id: str | None = Field(default=None, alias="spanId", max_length=32)
    correlation_id: CorrelationId | None = Field(default=None, alias="correlationId")
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)
    run_id: RunId | None = Field(default=None, alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    agent_session_id: AgentSessionId | None = Field(default=None, alias="agentSessionId")
    event_sequence: Sequence | None = Field(default=None, alias="eventSequence")
    service: str = Field(min_length=1, max_length=64)
    operation: str = Field(min_length=1, max_length=128)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)
    actor_kind: ActorKindV1 | None = Field(default=None, alias="actorKind")
    outcome: LogOutcomeV1 | None = None
    duration_ms: float | None = Field(default=None, alias="durationMs", ge=0)
    error_kind: str | None = Field(default=None, alias="errorKind", max_length=128)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> StructuredLogRecordV1:
        assert_supported_schema_version("structured_log_record", self.schema_version)
        if self.schema_version != STRUCTURED_LOG_RECORD_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported structured_log_record schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class DependencyStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    name: str = Field(min_length=1, max_length=64)
    state: DependencyStateV1
    required: bool = True
    latency_ms: float | None = Field(default=None, alias="latencyMs", ge=0)
    message: str | None = Field(default=None, max_length=512)
    checked_at: UtcTimestamp | None = Field(default=None, alias="checkedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> DependencyStatusV1:
        assert_supported_schema_version("dependency_status", self.schema_version)
        if self.schema_version != DEPENDENCY_STATUS_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported dependency_status schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class HealthResponseV1(BaseModel):
    """Liveness response — process is alive. Does not check dependencies."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    status: HealthStatusV1
    service: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=64)
    checked_at: UtcTimestamp | None = Field(default=None, alias="checkedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> HealthResponseV1:
        assert_supported_schema_version("health_response", self.schema_version)
        if self.schema_version != HEALTH_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported health_response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReadyResponseV1(BaseModel):
    """Readiness response — service can safely receive intended traffic."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    status: ReadyStatusV1
    service: str = Field(min_length=1, max_length=64)
    environment: str = Field(min_length=1, max_length=32)
    dependencies: list[DependencyStatusV1] = Field(default_factory=list)
    checked_at: UtcTimestamp | None = Field(default=None, alias="checkedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReadyResponseV1:
        assert_supported_schema_version("ready_response", self.schema_version)
        if self.schema_version != READY_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported ready_response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class MetricLabelPolicyV1(BaseModel):
    """Documents allowed metric labels and forbids unbounded cardinality labels."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    metric_name: str = Field(alias="metricName", min_length=1, max_length=128)
    metric_type: MetricTypeV1 = Field(alias="metricType")
    unit: str = Field(min_length=1, max_length=32)
    description: str = Field(min_length=1, max_length=512)
    allowed_labels: list[str] = Field(alias="allowedLabels", default_factory=list)
    source: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_schema_and_labels(self) -> MetricLabelPolicyV1:
        assert_supported_schema_version("metric_label_policy", self.schema_version)
        if self.schema_version != METRIC_LABEL_POLICY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported metric_label_policy schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        for label in self.allowed_labels:
            if label in FORBIDDEN_METRIC_LABELS:
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message=f"Forbidden high-cardinality metric label: {label}",
                    details={"label": label},
                )
            if label not in ALLOWED_METRIC_LABELS:
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message=f"Metric label not in allowlist: {label}",
                    details={"label": label},
                )
        return self
