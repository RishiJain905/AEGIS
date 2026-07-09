"""Phase 23 SCRIBE after-action report contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AgentSessionId,
    AgentTaskId,
    AssetId,
    EventId,
    EvidenceId,
    HypothesisId,
    IncidentId,
    ProposalId,
    RunId,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SCHEMA_VERSION,
    AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
    GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION,
    REPORT_CITATION_SCHEMA_VERSION,
    REPORT_CLAIM_SCHEMA_VERSION,
    REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION,
    REPORT_TIMELINE_ENTRY_SCHEMA_VERSION,
    REPORT_VERSION_SCHEMA_VERSION,
    TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ReportClaimCategoryV1(StrEnum):
    OBSERVED_FACT = "observed_fact"
    PERSISTED_EVENT = "persisted_event"
    DETECTION_SCORE = "detection_score"
    GRAPH_RISK = "graph_risk"
    INVESTIGATION_EVIDENCE = "investigation_evidence"
    ORACLE_HYPOTHESIS = "oracle_hypothesis"
    BASTION_PROPOSAL = "bastion_proposal"
    WARDEN_POLICY_DECISION = "warden_policy_decision"
    HUMAN_DECISION = "human_decision"
    AGENT_INFERENCE = "agent_inference"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"


class ReportCitationKindV1(StrEnum):
    EVENT = "event"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    PROPOSAL = "proposal"
    POLICY_DECISION = "policy_decision"
    MODEL_SCORE = "model_score"
    AGENT_TASK = "agent_task"
    AGENT_SESSION = "agent_session"
    ALERT = "alert"
    ASSET = "asset"


class ReportExportFormatV1(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class ReportGenerationStatusV1(StrEnum):
    COMPLETED = "completed"
    GROUNDING_FALLBACK = "grounding_fallback"
    FAILED = "failed"


class ReportCitationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    kind: ReportCitationKindV1
    reference_id: str = Field(alias="referenceId", min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    sequence: int | None = Field(default=None, ge=0)
    rationale: str = Field(default="", max_length=2048)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReportCitationV1:
        assert_supported_schema_version("report_citation", self.schema_version)
        if self.schema_version != REPORT_CITATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported report citation schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReportClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    claim_id: str = Field(alias="claimId", min_length=1, max_length=64)
    category: ReportClaimCategoryV1
    text: str = Field(min_length=1, max_length=4096)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: str | None = Field(default=None, max_length=1024)
    citations: list[ReportCitationV1] = Field(default_factory=list)
    grounded: bool = True
    rejection_reason: str | None = Field(default=None, alias="rejectionReason", max_length=1024)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReportClaimV1:
        assert_supported_schema_version("report_claim", self.schema_version)
        if self.schema_version != REPORT_CLAIM_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported report claim schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReportTimelineEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    sequence: int = Field(ge=0)
    event_id: EventId = Field(alias="eventId")
    event_type: str = Field(alias="eventType", min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    timestamp: UtcTimestamp
    status: str = Field(default="normal", max_length=64)
    related_evidence_ids: list[EvidenceId] = Field(
        alias="relatedEvidenceIds",
        default_factory=list,
    )
    related_hypothesis_ids: list[HypothesisId] = Field(
        alias="relatedHypothesisIds",
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReportTimelineEntryV1:
        assert_supported_schema_version("report_timeline_entry", self.schema_version)
        if self.schema_version != REPORT_TIMELINE_ENTRY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported report timeline entry schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AfterActionReportSourceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId = Field(alias="incidentId")
    source_sequence_from: int = Field(alias="sourceSequenceFrom", ge=0)
    source_sequence_to: int = Field(alias="sourceSequenceTo", ge=0)
    event_ids: list[EventId] = Field(alias="eventIds", default_factory=list)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", default_factory=list)
    hypothesis_ids: list[HypothesisId] = Field(alias="hypothesisIds", default_factory=list)
    proposal_ids: list[ProposalId] = Field(alias="proposalIds", default_factory=list)
    policy_decision_ids: list[str] = Field(alias="policyDecisionIds", default_factory=list)
    affected_asset_ids: list[AssetId] = Field(alias="affectedAssetIds", default_factory=list)
    alert_ids: list[str] = Field(alias="alertIds", default_factory=list)
    agent_session_ids: list[AgentSessionId] = Field(
        alias="agentSessionIds",
        default_factory=list,
    )
    timeline: list[ReportTimelineEntryV1] = Field(default_factory=list)
    investigation_summary: dict[str, Any] = Field(
        alias="investigationSummary",
        default_factory=dict,
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> AfterActionReportSourceV1:
        assert_supported_schema_version("after_action_report_source", self.schema_version)
        if self.schema_version != AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported after-action report source schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AfterActionReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId = Field(alias="incidentId")
    version_number: int = Field(alias="versionNumber", ge=1)
    title: str = Field(min_length=1, max_length=256)
    executive_summary: str = Field(alias="executiveSummary", min_length=1, max_length=8192)
    chronology_summary: str = Field(alias="chronologySummary", min_length=1, max_length=8192)
    claims: list[ReportClaimV1] = Field(default_factory=list)
    timeline: list[ReportTimelineEntryV1] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source: AfterActionReportSourceV1
    grounding_fallback: bool = Field(default=False, alias="groundingFallback")
    narrative_provider_id: str | None = Field(default=None, alias="narrativeProviderId")
    narrative_prompt_version: str | None = Field(default=None, alias="narrativePromptVersion")
    session_id: AgentSessionId | None = Field(default=None, alias="sessionId")
    task_id: AgentTaskId | None = Field(default=None, alias="taskId")
    checksum: str = Field(min_length=64, max_length=64)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AfterActionReportV1:
        assert_supported_schema_version("after_action_report", self.schema_version)
        if self.schema_version != AFTER_ACTION_REPORT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported after-action report schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReportVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId = Field(alias="incidentId")
    version_number: int = Field(alias="versionNumber", ge=1)
    report_id: str = Field(alias="reportId", min_length=1, max_length=64)
    status: ReportGenerationStatusV1
    source_sequence_from: int = Field(alias="sourceSequenceFrom", ge=0)
    source_sequence_to: int = Field(alias="sourceSequenceTo", ge=0)
    provider_id: str | None = Field(default=None, alias="providerId", max_length=64)
    prompt_version: str | None = Field(default=None, alias="promptVersion", max_length=64)
    session_id: AgentSessionId | None = Field(default=None, alias="sessionId")
    task_id: AgentTaskId | None = Field(default=None, alias="taskId")
    checksum: str = Field(min_length=64, max_length=64)
    grounding_fallback: bool = Field(default=False, alias="groundingFallback")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReportVersionV1:
        assert_supported_schema_version("report_version", self.schema_version)
        if self.schema_version != REPORT_VERSION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported report version schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ReportExportArtifactV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    report_version_id: str = Field(alias="reportVersionId", min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    format: ReportExportFormatV1
    object_key: str = Field(alias="objectKey", min_length=1, max_length=512)
    checksum: str = Field(min_length=64, max_length=64)
    content_type: str = Field(alias="contentType", min_length=1, max_length=128)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    workspace_version: str = Field(alias="workspaceVersion", min_length=1, max_length=32)
    report_schema_version: int = Field(alias="reportSchemaVersion", ge=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ReportExportArtifactV1:
        assert_supported_schema_version("report_export_artifact", self.schema_version)
        if self.schema_version != REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported report export artifact schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GroundingValidationResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    claim_id: str = Field(alias="claimId", min_length=1, max_length=64)
    valid: bool
    citation_results: list[dict[str, Any]] = Field(alias="citationResults", default_factory=list)
    rejection_reason: str | None = Field(default=None, alias="rejectionReason", max_length=1024)
    downgraded_category: ReportClaimCategoryV1 | None = Field(
        default=None,
        alias="downgradedCategory",
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> GroundingValidationResultV1:
        assert_supported_schema_version("grounding_validation_result", self.schema_version)
        if self.schema_version != GROUNDING_VALIDATION_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported grounding validation result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TriggerScribeRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(default="mock", alias="providerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    regenerate: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_schema_version(self) -> TriggerScribeRequestV1:
        assert_supported_schema_version("trigger_scribe_request", self.schema_version)
        if self.schema_version != TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trigger scribe request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
