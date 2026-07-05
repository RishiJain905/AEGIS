"""Domain event envelope and event-type registry."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AuthoredId,
    CausationId,
    CorrelationId,
    EventId,
    RunId,
    Sequence,
    SimTimestamp,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    DOMAIN_EVENT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ActorType(StrEnum):
    ASSET = "asset"
    AGENT = "agent"
    SYSTEM = "system"
    OPERATOR = "operator"


class ActorRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: ActorType
    id: AuthoredId


class DomainEventEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: EventId = Field(alias="eventId")
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    type: str = Field(min_length=1)
    schema_version: int = Field(alias="schemaVersion", ge=1)
    sim_time: SimTimestamp = Field(alias="simTime")
    recorded_at: UtcTimestamp = Field(alias="recordedAt")
    actor: ActorRef
    subject: ActorRef
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: TraceId = Field(alias="traceId")
    causation_id: CausationId | None = Field(default=None, alias="causationId")
    correlation_id: CorrelationId | None = Field(default=None, alias="correlationId")

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if not EventTypeRegistry.is_known_type(value):
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=f"Unknown event type: {value}",
                details={"type": value},
            )
        return value

    @model_validator(mode="after")
    def validate_schema_version(self) -> DomainEventEnvelopeV1:
        assert_supported_schema_version("domain_event", self.schema_version)
        if self.schema_version != DOMAIN_EVENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported domain event schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        expected_payload_version = EventTypeRegistry.payload_schema_version(self.type)
        payload_version = self.payload.get("schemaVersion")
        if payload_version is not None and payload_version != expected_payload_version:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Event payload schema version mismatch",
                details={
                    "type": self.type,
                    "expectedPayloadSchemaVersion": expected_payload_version,
                    "payloadSchemaVersion": payload_version,
                },
            )
        return self


class EventTypeRegistry:
    """Registry of known v1 event types and payload schema versions."""

    _TYPES: ClassVar[dict[str, int]] = {
        "sim.run.started": 1,
        "sim.run.paused": 1,
        "sim.run.resumed": 1,
        "sim.run.stopped": 1,
        "sim.checkpoint.created": 1,
        "sim.command.executed": 1,
        "sim.asset.status_changed": 1,
        "sim.branch.selected": 1,
        "sim.hidden_condition.revealed": 1,
        "sim.hidden_condition.triggered": 1,
        "telemetry.authentication.failed": 1,
        "telemetry.authentication.succeeded": 1,
        "telemetry.api.request": 1,
        "telemetry.health.check": 1,
        "telemetry.network.connection": 1,
        "telemetry.database.query": 1,
        "telemetry.deployment.event": 1,
        "telemetry.process.activity": 1,
        "telemetry.ai.inference": 1,
        "alert.created": 1,
        "incident.created": 1,
        "incident.state_changed": 1,
        "hypothesis.created": 1,
        "agent.session.started": 1,
        "agent.session.completed": 1,
        "agent.session.state_changed": 1,
        "agent.task.started": 1,
        "agent.task.completed": 1,
        "agent.task.failed": 1,
        "agent.tool.invoked": 1,
        "action.proposal.created": 1,
        "action.proposal.approved": 1,
        "action.executed": 1,
        "graph.snapshot.created": 1,
        "model.score.recorded": 1,
        "risk.score.computed": 1,
        "risk.projection.updated": 1,
    }

    @classmethod
    def is_known_type(cls, event_type: str) -> bool:
        return event_type in cls._TYPES

    @classmethod
    def payload_schema_version(cls, event_type: str) -> int:
        if event_type not in cls._TYPES:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=f"Unknown event type: {event_type}",
                details={"type": event_type},
            )
        return cls._TYPES[event_type]

    @classmethod
    def known_types(cls) -> frozenset[str]:
        return frozenset(cls._TYPES.keys())
