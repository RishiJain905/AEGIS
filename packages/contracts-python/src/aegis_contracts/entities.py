"""Base domain entity contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.detection import AlertEvidenceV1, RuleExplanationV1
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    ActionId,
    AgentSessionId,
    AlertId,
    ApprovalId,
    AssetId,
    AuthoredId,
    EventId,
    EvidenceId,
    HypothesisId,
    IncidentId,
    ModelId,
    ProposalId,
    Revision,
    RunId,
    ScenarioId,
    SimTimestamp,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    AGENT_SESSION_SCHEMA_VERSION,
    ALERT_SCHEMA_VERSION,
    APPROVAL_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    EXECUTED_ACTION_SCHEMA_VERSION,
    HYPOTHESIS_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    MODEL_MANIFEST_SCHEMA_VERSION,
    MODEL_SCORE_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class IncidentState(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    CONTAINMENT_PROPOSED = "containment_proposed"
    APPROVAL_PENDING = "approval_pending"
    CONTAINING = "containing"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AgentSessionState(StrEnum):
    QUEUED = "queued"
    GATHERING = "gathering"
    HYPOTHESIZING = "hypothesizing"
    VERIFYING = "verifying"
    PROPOSING = "proposing"
    APPROVAL_PENDING = "approval_pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(StrEnum):
    WATCHTOWER = "WATCHTOWER"
    TRACE = "TRACE"
    ORACLE = "ORACLE"
    BASTION = "BASTION"
    WARDEN = "WARDEN"
    SCRIBE = "SCRIBE"


class ActionClass(StrEnum):
    READ_ONLY = "class_0"
    LOW_IMPACT = "class_1"
    OPERATIONAL = "class_2"
    CRITICAL = "class_3"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ScenarioV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ScenarioId
    name: str = Field(min_length=1)
    description: str = ""
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScenarioV1:
        assert_supported_schema_version("scenario", self.schema_version)
        if self.schema_version != SCENARIO_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported scenario schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScenarioVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AuthoredId
    scenario_id: ScenarioId = Field(alias="scenarioId")
    version: str = Field(min_length=1)
    required_platform_version: str = Field(alias="requiredPlatformVersion")
    published_at: UtcTimestamp = Field(alias="publishedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScenarioVersionV1:
        assert_supported_schema_version("scenario_version", self.schema_version)
        if self.schema_version != SCENARIO_VERSION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported scenario version schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: RunId
    scenario_version_id: AuthoredId = Field(alias="scenarioVersionId")
    seed: int
    status: str = Field(min_length=1)
    started_at: UtcTimestamp = Field(alias="startedAt")
    sim_time: SimTimestamp = Field(alias="simTime")
    revision: Revision

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunV1:
        assert_supported_schema_version("run", self.schema_version)
        if self.schema_version != RUN_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AlertV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AlertId
    run_id: RunId = Field(alias="runId")
    title: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    source_event_id: EventId = Field(alias="sourceEventId")
    asset_id: AssetId = Field(alias="assetId")
    created_at: UtcTimestamp = Field(alias="createdAt")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    detector_id: str | None = Field(default=None, alias="detectorId")
    detector_version: str | None = Field(default=None, alias="detectorVersion")
    rule_id: str | None = Field(default=None, alias="ruleId")
    rule_version: str | None = Field(default=None, alias="ruleVersion")
    explanation: RuleExplanationV1 | None = None
    anomaly_explanation: dict[str, Any] | None = Field(default=None, alias="anomalyExplanation")
    model_version_id: ModelId | None = Field(default=None, alias="modelVersionId")
    evidence: AlertEvidenceV1 | None = None
    deduplication_key: str | None = Field(default=None, alias="deduplicationKey")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AlertV1:
        assert_supported_schema_version("alert", self.schema_version)
        if self.schema_version != ALERT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported alert schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class IncidentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: IncidentId
    run_id: RunId = Field(alias="runId")
    title: str = Field(min_length=1)
    state: IncidentState
    alert_ids: list[AlertId] = Field(alias="alertIds")
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")
    revision: Revision

    @model_validator(mode="after")
    def validate_schema_version(self) -> IncidentV1:
        assert_supported_schema_version("incident", self.schema_version)
        if self.schema_version != INCIDENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported incident schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class EvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: EvidenceId
    run_id: RunId = Field(alias="runId")
    source_event_id: EventId = Field(alias="sourceEventId")
    summary: str = Field(min_length=1)
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> EvidenceV1:
        assert_supported_schema_version("evidence", self.schema_version)
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported evidence schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class HypothesisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: HypothesisId
    incident_id: IncidentId = Field(alias="incidentId")
    current_revision_id: str | None = Field(default=None, alias="currentRevisionId")
    family: str | None = Field(default=None, max_length=64)
    status: str = Field(default="active", max_length=32)
    statement: str | None = Field(default=None, min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", default_factory=list)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> HypothesisV1:
        assert_supported_schema_version("hypothesis", self.schema_version)
        if self.schema_version not in {1, HYPOTHESIS_SCHEMA_VERSION}:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported hypothesis schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.schema_version == 1:
            if not self.statement:
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message="Hypothesis v1 requires statement",
                    details={"schemaVersion": self.schema_version},
                )
            if self.confidence is None:
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message="Hypothesis v1 requires confidence",
                    details={"schemaVersion": self.schema_version},
                )
        if self.schema_version == HYPOTHESIS_SCHEMA_VERSION and not self.current_revision_id:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Hypothesis v2 requires currentRevisionId",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentSessionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AgentSessionId
    incident_id: IncidentId = Field(alias="incidentId")
    role: AgentRole
    state: AgentSessionState
    trace_id: TraceId = Field(alias="traceId")
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentSessionV1:
        assert_supported_schema_version("agent_session", self.schema_version)
        if self.schema_version != AGENT_SESSION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent session schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ActionProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ProposalId
    incident_id: IncidentId = Field(alias="incidentId")
    agent_session_id: AgentSessionId = Field(alias="agentSessionId")
    action_class: ActionClass = Field(alias="actionClass")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    command: str = Field(min_length=1)
    scenario_command: str | None = Field(default=None, alias="scenarioCommand")
    current_revision_id: str | None = Field(default=None, alias="currentRevisionId")
    status: ProposalStatus
    rationale: str = ""
    revision: Revision
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ActionProposalV1:
        assert_supported_schema_version("action_proposal", self.schema_version)
        if self.schema_version not in {1, ACTION_PROPOSAL_SCHEMA_VERSION}:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported action proposal schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.schema_version == ACTION_PROPOSAL_SCHEMA_VERSION and not self.current_revision_id:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Action proposal v2 requires currentRevisionId",
                details={"schemaVersion": self.schema_version},
            )
        if self.schema_version == ACTION_PROPOSAL_SCHEMA_VERSION and not self.scenario_command:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Action proposal v2 requires scenarioCommand",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ApprovalV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ApprovalId
    proposal_id: ProposalId = Field(alias="proposalId")
    decision: ApprovalDecision
    approver_id: str = Field(alias="approverId", min_length=1)
    proposal_revision: Revision = Field(alias="proposalRevision")
    decided_at: UtcTimestamp = Field(alias="decidedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ApprovalV1:
        assert_supported_schema_version("approval", self.schema_version)
        if self.schema_version != APPROVAL_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported approval schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ExecutedActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ActionId
    proposal_id: ProposalId = Field(alias="proposalId")
    run_id: RunId = Field(alias="runId")
    result_event_id: EventId = Field(alias="resultEventId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1)
    executed_at: UtcTimestamp = Field(alias="executedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ExecutedActionV1:
        assert_supported_schema_version("executed_action", self.schema_version)
        if self.schema_version != EXECUTED_ACTION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported executed action schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ModelId
    semantic_version: str = Field(alias="semanticVersion", min_length=1)
    algorithm: str = Field(min_length=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    artifact_checksum: str = Field(alias="artifactChecksum", min_length=1)
    artifact_object_key: str = Field(alias="artifactObjectKey", min_length=1)
    evaluation_metrics: dict[str, Any] = Field(
        default_factory=dict,
        alias="evaluationMetrics",
    )
    known_limitations: list[str] = Field(default_factory=list, alias="knownLimitations")
    created_at: UtcTimestamp = Field(alias="createdAt")
    hyperparameters: dict[str, Any] | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_band_thresholds: dict[str, float] | None = Field(
        default=None,
        alias="riskBandThresholds",
    )
    training_run_id: str | None = Field(default=None, alias="trainingRunId")
    code_revision: str | None = Field(default=None, alias="codeRevision")
    sklearn_version: str | None = Field(default=None, alias="sklearnVersion")
    dataset_ids: list[str] | None = Field(default=None, alias="datasetIds")
    approval_status: str | None = Field(default=None, alias="approvalStatus")
    predecessor_model_id: ModelId | None = Field(default=None, alias="predecessorModelId")
    score_semantics: str | None = Field(default=None, alias="scoreSemantics")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ModelManifestV1:
        assert_supported_schema_version("model_manifest", self.schema_version)
        if self.schema_version != MODEL_MANIFEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported model manifest schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelScoreV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    model_version_id: ModelId = Field(alias="modelVersionId")
    entity_id: AssetId = Field(alias="entityId")
    score: float = Field(ge=0.0, le=1.0)
    risk_band: str = Field(alias="riskBand", min_length=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    explanation: dict[str, Any] = Field(default_factory=dict)
    scored_at: UtcTimestamp = Field(alias="scoredAt")
    source_event_id: EventId | None = Field(default=None, alias="sourceEventId")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ModelScoreV1:
        assert_supported_schema_version("model_score", self.schema_version)
        if self.schema_version != MODEL_SCORE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported model score schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
