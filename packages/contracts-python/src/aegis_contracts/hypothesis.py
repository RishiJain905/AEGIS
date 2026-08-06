"""Phase 21 ORACLE hypothesis contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AgentSessionId,
    AgentTaskId,
    CitableEvidenceId,
    HypothesisId,
    IncidentId,
    RunId,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    CONFIDENCE_ASSESSMENT_SCHEMA_VERSION,
    CONTRADICTION_LINK_SCHEMA_VERSION,
    HYPOTHESIS_CLAIM_SCHEMA_VERSION,
    HYPOTHESIS_COMPARISON_SCHEMA_VERSION,
    HYPOTHESIS_REVISION_SCHEMA_VERSION,
    TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
    VERIFICATION_REQUEST_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class HypothesisFamilyV1(StrEnum):
    LATERAL_MOVEMENT = "lateral_movement"
    CREDENTIAL_ABUSE = "credential_abuse"
    BENIGN_ANOMALY = "benign_anomaly"
    SUPPLY_CHAIN = "supply_chain"
    INSIDER_THREAT = "insider_threat"
    DATA_EXFILTRATION = "data_exfiltration"


class ClaimKindV1(StrEnum):
    OBSERVED_FACT = "observed_fact"
    MODEL_SCORE = "model_score"
    GRAPH_RISK = "graph_risk"
    AGENT_INFERENCE = "agent_inference"
    UNSUPPORTED_CLAIM = "unsupported_claim"


class HypothesisStatusV1(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class HypothesisClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    kind: ClaimKindV1
    text: str = Field(min_length=1, max_length=2048)
    evidence_ids: list[CitableEvidenceId] = Field(alias="evidenceIds", default_factory=list)
    attachment_ids: list[str] = Field(alias="attachmentIds", default_factory=list)
    is_assumption: bool = Field(alias="isAssumption", default=False)

    @model_validator(mode="after")
    def validate_schema_version(self) -> HypothesisClaimV1:
        assert_supported_schema_version("hypothesis_claim", self.schema_version)
        if self.schema_version != HYPOTHESIS_CLAIM_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported hypothesis claim schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ConfidenceAssessmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    point: float = Field(ge=0.0, le=1.0)
    min_value: float = Field(alias="min", ge=0.0, le=1.0)
    max_value: float = Field(alias="max", ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    contradiction_penalty: float = Field(alias="contradictionPenalty", ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ConfidenceAssessmentV1:
        assert_supported_schema_version("confidence_assessment", self.schema_version)
        if self.schema_version != CONFIDENCE_ASSESSMENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported confidence assessment schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self

    @model_validator(mode="after")
    def validate_range(self) -> ConfidenceAssessmentV1:
        if self.min_value > self.max_value:
            msg = "Confidence min cannot exceed max"
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=msg,
                details={"min": self.min_value, "max": self.max_value},
            )
        if not (self.min_value <= self.point <= self.max_value):
            msg = "Confidence point must fall within min/max range"
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=msg,
                details={
                    "point": self.point,
                    "min": self.min_value,
                    "max": self.max_value,
                },
            )
        return self


class ContradictionLinkV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    supporting_evidence_ids: list[CitableEvidenceId] = Field(
        alias="supportingEvidenceIds",
        default_factory=list,
    )
    contradicting_evidence_ids: list[CitableEvidenceId] = Field(
        alias="contradictingEvidenceIds",
        default_factory=list,
    )
    supporting_attachment_ids: list[str] = Field(
        alias="supportingAttachmentIds",
        default_factory=list,
    )
    contradicting_attachment_ids: list[str] = Field(
        alias="contradictingAttachmentIds",
        default_factory=list,
    )
    rationale: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ContradictionLinkV1:
        assert_supported_schema_version("contradiction_link", self.schema_version)
        if self.schema_version != CONTRADICTION_LINK_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported contradiction link schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class HypothesisRevisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    hypothesis_id: HypothesisId = Field(alias="hypothesisId")
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    revision_number: int = Field(alias="revisionNumber", ge=1)
    claim: str = Field(min_length=1, max_length=4096)
    family: HypothesisFamilyV1
    confidence: ConfidenceAssessmentV1
    claims: list[HypothesisClaimV1] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[CitableEvidenceId] = Field(
        alias="supportingEvidenceIds",
        default_factory=list,
    )
    contradicting_evidence_ids: list[CitableEvidenceId] = Field(
        alias="contradictingEvidenceIds",
        default_factory=list,
    )
    unknowns: list[str] = Field(default_factory=list)
    predictions: list[str] = Field(default_factory=list)
    contradiction_links: list[ContradictionLinkV1] = Field(
        alias="contradictionLinks",
        default_factory=list,
    )
    status: HypothesisStatusV1 = HypothesisStatusV1.ACTIVE
    rationale: str = Field(min_length=1, max_length=2048)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> HypothesisRevisionV1:
        assert_supported_schema_version("hypothesis_revision", self.schema_version)
        if self.schema_version != HYPOTHESIS_REVISION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported hypothesis revision schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class HypothesisComparisonEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    hypothesis_id: HypothesisId = Field(alias="hypothesisId")
    revision_id: str = Field(alias="revisionId", min_length=1, max_length=64)
    shared_evidence_ids: list[CitableEvidenceId] = Field(
        alias="sharedEvidenceIds",
        default_factory=list,
    )
    unique_evidence_ids: list[CitableEvidenceId] = Field(
        alias="uniqueEvidenceIds",
        default_factory=list,
    )
    contradicting_evidence_ids: list[CitableEvidenceId] = Field(
        alias="contradictingEvidenceIds",
        default_factory=list,
    )
    confidence_point: float = Field(alias="confidencePoint", ge=0.0, le=1.0)


class HypothesisComparisonV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    entries: list[HypothesisComparisonEntryV1] = Field(min_length=2)
    summary: str = Field(min_length=1, max_length=4096)
    matrix: dict[str, Any] = Field(default_factory=dict)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> HypothesisComparisonV1:
        assert_supported_schema_version("hypothesis_comparison", self.schema_version)
        if self.schema_version != HYPOTHESIS_COMPARISON_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported hypothesis comparison schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class VerificationRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    hypothesis_id: HypothesisId = Field(alias="hypothesisId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    purpose: str = Field(min_length=1, max_length=2048)
    target_evidence_ids: list[CitableEvidenceId] = Field(
        alias="targetEvidenceIds",
        default_factory=list,
    )
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> VerificationRequestV1:
        assert_supported_schema_version("verification_request", self.schema_version)
        if self.schema_version != VERIFICATION_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported verification request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TriggerOracleRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(default="mock", alias="providerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    revision_mode: bool = Field(default=False, alias="revisionMode")

    @model_validator(mode="after")
    def validate_schema_version(self) -> TriggerOracleRequestV1:
        assert_supported_schema_version("trigger_oracle_request", self.schema_version)
        if self.schema_version != TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trigger oracle request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
