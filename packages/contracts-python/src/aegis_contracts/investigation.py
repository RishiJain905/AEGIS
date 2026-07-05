"""Phase 20 WATCHTOWER and TRACE investigation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import ActionProposalV1, HypothesisV1
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.hypothesis import (
    HypothesisComparisonV1,
    HypothesisRevisionV1,
    VerificationRequestV1,
)
from aegis_contracts.primitives import (
    AgentSessionId,
    AgentTaskId,
    AlertId,
    AssetId,
    EvidenceId,
    IncidentId,
    RunId,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.proposals import PolicyDecisionV1, ProposalRevisionV1
from aegis_contracts.versioning import (
    AGENT_GRAPH_OVERLAY_SCHEMA_VERSION,
    CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION,
    EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
    INVESTIGATION_DETAIL_SCHEMA_VERSION,
    INVESTIGATION_NOTE_SCHEMA_VERSION,
    TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION,
    TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
    WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class TriageEscalationLevel(StrEnum):
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    URGENT = "urgent"


class EvidenceSourceType(StrEnum):
    EVENT = "event"
    ALERT = "alert"
    ASSET = "asset"
    RISK_PATH = "risk_path"
    EXISTING_EVIDENCE = "existing_evidence"


class AlertCorrelationDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    alert_ids: list[AlertId] = Field(alias="alertIds")
    decision: str = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=1, max_length=2048)
    factors: list[str] = Field(default_factory=list)


class WatchtowerTriageResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    run_id: RunId = Field(alias="runId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    alert_summaries: list[dict[str, Any]] = Field(alias="alertSummaries", default_factory=list)
    grouped_alert_ids: list[AlertId] = Field(alias="groupedAlertIds", default_factory=list)
    separated_alert_ids: list[AlertId] = Field(alias="separatedAlertIds", default_factory=list)
    correlation_decisions: list[AlertCorrelationDecisionV1] = Field(
        alias="correlationDecisions",
        default_factory=list,
    )
    escalation: TriageEscalationLevel
    escalation_rationale: str = Field(alias="escalationRationale", min_length=1, max_length=2048)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", default_factory=list)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> WatchtowerTriageResultV1:
        assert_supported_schema_version("watchtower_triage_result", self.schema_version)
        if self.schema_version != WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported watchtower triage result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TraceSearchStepV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tool_name: str = Field(alias="toolName", min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    purpose: str = Field(min_length=1, max_length=512)


class TraceInvestigationPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    run_id: RunId = Field(alias="runId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    seed_asset_ids: list[AssetId] = Field(alias="seedAssetIds", default_factory=list)
    time_window_start_sequence: int | None = Field(
        default=None,
        alias="timeWindowStartSequence",
        ge=0,
    )
    time_window_end_sequence: int | None = Field(
        default=None,
        alias="timeWindowEndSequence",
        ge=0,
    )
    max_hops: int = Field(alias="maxHops", ge=1, le=8)
    max_tool_calls: int = Field(alias="maxToolCalls", ge=1, le=50)
    max_tokens: int = Field(alias="maxTokens", ge=1, le=100_000)
    search_steps: list[TraceSearchStepV1] = Field(alias="searchSteps", default_factory=list)
    rationale: str = Field(min_length=1, max_length=2048)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> TraceInvestigationPlanV1:
        assert_supported_schema_version("trace_investigation_plan", self.schema_version)
        if self.schema_version != TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trace investigation plan schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class EvidenceProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_type: EvidenceSourceType = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId", min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=2048)
    collected_by_tool: str | None = Field(default=None, alias="collectedByTool")
    collected_at_sequence: int | None = Field(default=None, alias="collectedAtSequence", ge=0)


class EvidenceAttachmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    provenance: EvidenceProvenanceV1
    evidence_id: EvidenceId | None = Field(default=None, alias="evidenceId")
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    is_contradiction: bool = Field(alias="isContradiction", default=False)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=2048)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> EvidenceAttachmentV1:
        assert_supported_schema_version("evidence_attachment", self.schema_version)
        if self.schema_version != EVIDENCE_ATTACHMENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported evidence attachment schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CandidateAffectedAssetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    asset_id: AssetId = Field(alias="assetId")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", default_factory=list)
    rationale: str = Field(min_length=1, max_length=2048)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> CandidateAffectedAssetV1:
        assert_supported_schema_version("candidate_affected_asset", self.schema_version)
        if self.schema_version != CANDIDATE_AFFECTED_ASSET_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported candidate affected asset schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class InvestigationNoteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    note: str = Field(min_length=1, max_length=4096)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> InvestigationNoteV1:
        assert_supported_schema_version("investigation_note", self.schema_version)
        if self.schema_version != INVESTIGATION_NOTE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported investigation note schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GraphOverlayHighlightV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    entity_id: str = Field(alias="entityId", min_length=1, max_length=128)
    entity_type: str = Field(alias="entityType", min_length=1, max_length=32)
    highlight_kind: str = Field(alias="highlightKind", min_length=1, max_length=32)
    label: str = Field(default="", max_length=256)


class AgentGraphOverlayV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    run_id: RunId = Field(alias="runId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    highlights: list[GraphOverlayHighlightV1] = Field(default_factory=list)
    edge_highlights: list[GraphOverlayHighlightV1] = Field(
        alias="edgeHighlights",
        default_factory=list,
    )
    rationale: str = Field(min_length=1, max_length=2048)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentGraphOverlayV1:
        assert_supported_schema_version("agent_graph_overlay", self.schema_version)
        if self.schema_version != AGENT_GRAPH_OVERLAY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent graph overlay schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class InvestigationDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    incident_id: IncidentId = Field(alias="incidentId")
    run_id: RunId = Field(alias="runId")
    triage_results: list[WatchtowerTriageResultV1] = Field(
        alias="triageResults",
        default_factory=list,
    )
    plans: list[TraceInvestigationPlanV1] = Field(default_factory=list)
    evidence_attachments: list[EvidenceAttachmentV1] = Field(
        alias="evidenceAttachments",
        default_factory=list,
    )
    notes: list[InvestigationNoteV1] = Field(default_factory=list)
    candidate_assets: list[CandidateAffectedAssetV1] = Field(
        alias="candidateAssets",
        default_factory=list,
    )
    overlays: list[AgentGraphOverlayV1] = Field(default_factory=list)
    hypotheses: list[HypothesisV1] = Field(default_factory=list)
    hypothesis_revisions: list[HypothesisRevisionV1] = Field(
        alias="hypothesisRevisions",
        default_factory=list,
    )
    hypothesis_comparisons: list[HypothesisComparisonV1] = Field(
        alias="hypothesisComparisons",
        default_factory=list,
    )
    verification_requests: list[VerificationRequestV1] = Field(
        alias="verificationRequests",
        default_factory=list,
    )
    proposals: list[ActionProposalV1] = Field(default_factory=list)
    proposal_revisions: list[ProposalRevisionV1] = Field(
        alias="proposalRevisions",
        default_factory=list,
    )
    policy_decisions: list[PolicyDecisionV1] = Field(
        alias="policyDecisions",
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> InvestigationDetailV1:
        assert_supported_schema_version("investigation_detail", self.schema_version)
        if self.schema_version not in {1, 2, INVESTIGATION_DETAIL_SCHEMA_VERSION}:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported investigation detail schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TriggerWatchtowerRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    alert_ids: list[AlertId] = Field(alias="alertIds", default_factory=list)
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(default="mock", alias="providerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_schema_version(self) -> TriggerWatchtowerRequestV1:
        assert_supported_schema_version("trigger_watchtower_request", self.schema_version)
        if self.schema_version != TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trigger watchtower request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
