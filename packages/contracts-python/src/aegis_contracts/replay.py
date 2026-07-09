"""Phase 25 snapshot and replay engine contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import (
    ActionProposalV1,
    AgentSessionV1,
    ApprovalV1,
    EvidenceV1,
    ExecutedActionV1,
    IncidentV1,
    RunV1,
)
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.primitives import (
    EventId,
    IncidentId,
    ReplaySnapshotId,
    RunId,
    Sequence,
    SimTimestamp,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    REPLAY_CURSOR_RANGE_SCHEMA_VERSION,
    REPLAY_CURSOR_SCHEMA_VERSION,
    REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION,
    REPLAY_PROVENANCE_SCHEMA_VERSION,
    REPLAY_SNAPSHOT_SCHEMA_VERSION,
    REPLAY_STATE_SCHEMA_VERSION,
    SNAPSHOT_MANIFEST_SCHEMA_VERSION,
    STATE_DIFF_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class SnapshotTriggerReasonV1(StrEnum):
    SEQUENCE_INTERVAL = "sequence_interval"
    RUN_PAUSED = "run_paused"
    RUN_COMPLETED = "run_completed"
    EXPLICIT_REQUEST = "explicit_request"
    WORKER_BACKFILL = "worker_backfill"


class SnapshotCompressionV1(StrEnum):
    NONE = "none"
    GZIP = "gzip"


class ReplayModeV1(StrEnum):
    FROM_EVENTS = "from_events"
    FROM_SNAPSHOT_PLUS_EVENTS = "from_snapshot_plus_events"


class ReplayErrorCode(StrEnum):
    SNAPSHOT_CHECKSUM_MISMATCH = "SNAPSHOT_CHECKSUM_MISMATCH"
    SNAPSHOT_INCOMPATIBLE = "SNAPSHOT_INCOMPATIBLE"
    SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
    REPLAY_SEQUENCE_GAP = "REPLAY_SEQUENCE_GAP"
    REPLAY_DUPLICATE_EVENT = "REPLAY_DUPLICATE_EVENT"
    REPLAY_LIVE_MUTATION_FORBIDDEN = "REPLAY_LIVE_MUTATION_FORBIDDEN"
    REPLAY_VALIDATION_FAILED = "REPLAY_VALIDATION_FAILED"
    REPLAY_NOT_FOUND = "REPLAY_NOT_FOUND"


class ReplayRiskScoreV1(BaseModel):
    """Compact risk projection entry for replay state."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: str = Field(alias="assetId", min_length=1, max_length=128)
    score: float = Field(ge=0.0, le=1.0)
    revision: int = Field(ge=0)


class ReplayReportRefV1(BaseModel):
    """Persisted report reference reconstructed during replay (no regeneration)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    report_id: str = Field(alias="reportId", min_length=1, max_length=64)
    report_version_id: str = Field(alias="reportVersionId", min_length=1, max_length=64)
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    status: str = Field(min_length=1, max_length=64)
    checksum: str | None = Field(default=None, max_length=128)


class ReplayAgentArtifactRefV1(BaseModel):
    """Persisted agent/LLM artifact reference — never regenerated during replay."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    artifact_id: str = Field(alias="artifactId", min_length=1, max_length=64)
    agent_session_id: str = Field(alias="agentSessionId", min_length=1, max_length=128)
    artifact_type: str = Field(alias="artifactType", min_length=1, max_length=64)
    object_key: str | None = Field(default=None, alias="objectKey", max_length=1024)
    checksum: str | None = Field(default=None, max_length=128)


class ReplayAuditEventRefV1(BaseModel):
    """Audit-relevant event reference reconstructed from authoritative history."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: EventId = Field(alias="eventId")
    sequence: Sequence
    event_type: str = Field(alias="eventType", min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=512)


class ReplayCursorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    sim_time: SimTimestamp | None = Field(default=None, alias="simTime")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReplayCursorV1:
        assert_supported_schema_version("replay_cursor", self.schema_version)
        if self.schema_version != REPLAY_CURSOR_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay cursor schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReplayCursorRangeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: Sequence = Field(alias="fromSequence")
    to_sequence: Sequence = Field(alias="toSequence")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")

    @model_validator(mode="after")
    def validate_range(self) -> ReplayCursorRangeV1:
        assert_supported_schema_version("replay_cursor_range", self.schema_version)
        if self.schema_version != REPLAY_CURSOR_RANGE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay cursor range schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.to_sequence < self.from_sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="toSequence must be >= fromSequence",
                details={
                    "fromSequence": self.from_sequence,
                    "toSequence": self.to_sequence,
                },
            )
        return self


class ReplayProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    mode: ReplayModeV1
    snapshot_id: ReplaySnapshotId | None = Field(default=None, alias="snapshotId")
    snapshot_sequence: Sequence | None = Field(default=None, alias="snapshotSequence")
    applied_from_sequence: Sequence = Field(alias="appliedFromSequence")
    applied_to_sequence: Sequence = Field(alias="appliedToSequence")
    applied_event_count: int = Field(alias="appliedEventCount", ge=0)
    fallback_reason: str | None = Field(default=None, alias="fallbackReason", max_length=512)
    reconstructed_at: UtcTimestamp = Field(alias="reconstructedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReplayProvenanceV1:
        assert_supported_schema_version("replay_provenance", self.schema_version)
        if self.schema_version != REPLAY_PROVENANCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay provenance schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.applied_to_sequence < self.applied_from_sequence and self.applied_event_count > 0:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="appliedToSequence must be >= appliedFromSequence when events applied",
                details={
                    "appliedFromSequence": self.applied_from_sequence,
                    "appliedToSequence": self.applied_to_sequence,
                },
            )
        return self


class ReplayStateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    cursor: ReplayCursorV1
    run: RunV1 | None = None
    graph: GraphSnapshotV1 | None = None
    incidents: list[IncidentV1] = Field(default_factory=list)
    evidence: list[EvidenceV1] = Field(default_factory=list)
    risk_scores: list[ReplayRiskScoreV1] = Field(alias="riskScores", default_factory=list)
    agent_sessions: list[AgentSessionV1] = Field(alias="agentSessions", default_factory=list)
    agent_artifacts: list[ReplayAgentArtifactRefV1] = Field(
        alias="agentArtifacts",
        default_factory=list,
    )
    proposals: list[ActionProposalV1] = Field(default_factory=list)
    approvals: list[ApprovalV1] = Field(default_factory=list)
    executed_actions: list[ExecutedActionV1] = Field(alias="executedActions", default_factory=list)
    reports: list[ReplayReportRefV1] = Field(default_factory=list)
    audit_events: list[ReplayAuditEventRefV1] = Field(alias="auditEvents", default_factory=list)
    state_digest: str = Field(alias="stateDigest", min_length=1, max_length=128)
    provenance: ReplayProvenanceV1

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReplayStateV1:
        assert_supported_schema_version("replay_state", self.schema_version)
        if self.schema_version != REPLAY_STATE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay state schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.cursor.run_id != self.run_id or self.provenance.run_id != self.run_id:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="runId must match cursor and provenance",
                details={"runId": self.run_id},
            )
        return self


class ReplaySnapshotV1(BaseModel):
    """Durable multi-domain projection used as a replay acceleration artifact."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ReplaySnapshotId
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    sim_time: SimTimestamp = Field(alias="simTime")
    scenario_version_id: str = Field(alias="scenarioVersionId", min_length=1, max_length=128)
    engine_version: str = Field(alias="engineVersion", min_length=1, max_length=64)
    projector_version: str = Field(alias="projectorVersion", min_length=1, max_length=64)
    workspace_version: str = Field(alias="workspaceVersion", min_length=1, max_length=64)
    event_range_from: Sequence = Field(alias="eventRangeFrom")
    event_range_to: Sequence = Field(alias="eventRangeTo")
    state: ReplayStateV1
    state_digest: str = Field(alias="stateDigest", min_length=1, max_length=128)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_snapshot(self) -> ReplaySnapshotV1:
        assert_supported_schema_version("replay_snapshot", self.schema_version)
        if self.schema_version != REPLAY_SNAPSHOT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay snapshot schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.run_id != self.state.run_id:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="snapshot runId must match embedded state runId",
                details={"runId": self.run_id, "stateRunId": self.state.run_id},
            )
        if self.sequence != self.state.cursor.sequence:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="snapshot sequence must match embedded state cursor sequence",
                details={"sequence": self.sequence, "cursorSequence": self.state.cursor.sequence},
            )
        if self.event_range_to < self.event_range_from:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="eventRangeTo must be >= eventRangeFrom",
                details={
                    "eventRangeFrom": self.event_range_from,
                    "eventRangeTo": self.event_range_to,
                },
            )
        return self


class SnapshotManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    snapshot_id: ReplaySnapshotId = Field(alias="snapshotId")
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    sim_time: SimTimestamp = Field(alias="simTime")
    scenario_version_id: str = Field(alias="scenarioVersionId", min_length=1, max_length=128)
    engine_version: str = Field(alias="engineVersion", min_length=1, max_length=64)
    projector_version: str = Field(alias="projectorVersion", min_length=1, max_length=64)
    workspace_version: str = Field(alias="workspaceVersion", min_length=1, max_length=64)
    event_range_from: Sequence = Field(alias="eventRangeFrom")
    event_range_to: Sequence = Field(alias="eventRangeTo")
    checksum: str = Field(min_length=1, max_length=128)
    compression: SnapshotCompressionV1
    content_type: str = Field(alias="contentType", min_length=1, max_length=256)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    object_key: str = Field(alias="objectKey", min_length=1, max_length=1024)
    state_digest: str = Field(alias="stateDigest", min_length=1, max_length=128)
    trigger_reason: SnapshotTriggerReasonV1 = Field(alias="triggerReason")
    retention_class: str = Field(alias="retentionClass", min_length=1, max_length=64)
    created_at: UtcTimestamp = Field(alias="createdAt")
    compatible: bool = True

    @model_validator(mode="after")
    def validate_manifest(self) -> SnapshotManifestV1:
        assert_supported_schema_version("snapshot_manifest", self.schema_version)
        if self.schema_version != SNAPSHOT_MANIFEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported snapshot manifest schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.event_range_to < self.event_range_from:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="eventRangeTo must be >= eventRangeFrom",
                details={
                    "eventRangeFrom": self.event_range_from,
                    "eventRangeTo": self.event_range_to,
                },
            )
        return self


class StateDiffEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: str = Field(min_length=1, max_length=512)
    change_type: str = Field(alias="changeType", min_length=1, max_length=32)
    before: Any | None = None
    after: Any | None = None


class StateDiffV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_cursor: ReplayCursorV1 = Field(alias="fromCursor")
    to_cursor: ReplayCursorV1 = Field(alias="toCursor")
    entries: list[StateDiffEntryV1] = Field(default_factory=list)
    from_digest: str = Field(alias="fromDigest", min_length=1, max_length=128)
    to_digest: str = Field(alias="toDigest", min_length=1, max_length=128)
    equivalent: bool

    @model_validator(mode="after")
    def validate_schema_version(self) -> StateDiffV1:
        assert_supported_schema_version("state_diff", self.schema_version)
        if self.schema_version != STATE_DIFF_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported state diff schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.from_cursor.run_id != self.run_id or self.to_cursor.run_id != self.run_id:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="diff cursors must match runId",
                details={"runId": self.run_id},
            )
        return self


class ReplayEquivalenceResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    live_digest: str = Field(alias="liveDigest", min_length=1, max_length=128)
    reconstructed_digest: str = Field(alias="reconstructedDigest", min_length=1, max_length=128)
    equivalent: bool
    diff: StateDiffV1 | None = None
    provenance: ReplayProvenanceV1
    checked_at: UtcTimestamp = Field(alias="checkedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReplayEquivalenceResultV1:
        assert_supported_schema_version("replay_equivalence_result", self.schema_version)
        if self.schema_version != REPLAY_EQUIVALENCE_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported replay equivalence result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
