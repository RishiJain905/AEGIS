"""Phase 22 BASTION/WARDEN proposal and policy contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import ActionClass, AgentRole, IncidentState
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AgentSessionId,
    AgentTaskId,
    AssetId,
    EvidenceId,
    HypothesisId,
    IncidentId,
    ProposalId,
    RunId,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    APPROVAL_REQUIREMENT_SCHEMA_VERSION,
    POLICY_DECISION_SCHEMA_VERSION,
    POLICY_INPUT_SCHEMA_VERSION,
    PROPOSAL_REVISION_SCHEMA_VERSION,
    RESPONSE_OPTION_SCHEMA_VERSION,
    TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
    TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ScenarioCommandTemplateV1(StrEnum):
    OBSERVE = "observe"
    INCREASE_MONITORING = "increase_monitoring"
    ISOLATE = "isolate"
    REVOKE_CREDENTIALS = "revoke_credentials"
    RESTRICT_ACCESS = "restrict_access"
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"


class PolicyOutcomeV1(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    APPROVAL_REQUIRED = "approval_required"


class PolicyReasonCodeV1(StrEnum):
    ALLOWED_READ_ONLY = "allowed_read_only"
    ALLOWED_LOW_IMPACT = "allowed_low_impact"
    APPROVAL_REQUIRED_OPERATIONAL = "approval_required_operational"
    APPROVAL_REQUIRED_CRITICAL = "approval_required_critical"
    BLOCKED_UNKNOWN_COMMAND = "blocked_unknown_command"
    BLOCKED_MALFORMED_COMMAND = "blocked_malformed_command"
    BLOCKED_SCENARIO_RESTRICTION = "blocked_scenario_restriction"
    BLOCKED_CRITICALITY_THRESHOLD = "blocked_criticality_threshold"
    BLOCKED_STALE_REVISION = "blocked_stale_revision"
    BLOCKED_INVALID_ACTION_CLASS = "blocked_invalid_action_class"
    BLOCKED_INCIDENT_STATE = "blocked_incident_state"


class ResponseOptionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    option_id: str = Field(alias="optionId", min_length=1, max_length=64)
    scenario_command: ScenarioCommandTemplateV1 = Field(alias="scenarioCommand")
    action_class: ActionClass = Field(alias="actionClass")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    affected_asset_ids: list[AssetId] = Field(alias="affectedAssetIds", default_factory=list)
    evidence_ids: list[EvidenceId] = Field(alias="evidenceIds", default_factory=list)
    hypothesis_ids: list[HypothesisId] = Field(alias="hypothesisIds", default_factory=list)
    expected_benefit: str = Field(alias="expectedBenefit", min_length=1, max_length=2048)
    operational_cost: str = Field(alias="operationalCost", min_length=1, max_length=2048)
    reversibility: str = Field(min_length=1, max_length=1024)
    prerequisites: list[str] = Field(default_factory=list)
    monitoring_plan: str = Field(alias="monitoringPlan", min_length=1, max_length=2048)
    expected_consequences: str = Field(alias="expectedConsequences", min_length=1, max_length=2048)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: str = Field(min_length=1, max_length=1024)
    rationale: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ResponseOptionV1:
        assert_supported_schema_version("response_option", self.schema_version)
        if self.schema_version != RESPONSE_OPTION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported response option schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ProposalRevisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    proposal_id: ProposalId = Field(alias="proposalId")
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    revision_number: int = Field(alias="revisionNumber", ge=1)
    response_options: list[ResponseOptionV1] = Field(alias="responseOptions", min_length=1)
    selected_option_id: str = Field(alias="selectedOptionId", min_length=1, max_length=64)
    rationale: str = Field(min_length=1, max_length=4096)
    risk_tradeoffs: str = Field(alias="riskTradeoffs", min_length=1, max_length=4096)
    linked_hypothesis_ids: list[HypothesisId] = Field(
        alias="linkedHypothesisIds",
        default_factory=list,
    )
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ProposalRevisionV1:
        assert_supported_schema_version("proposal_revision", self.schema_version)
        if self.schema_version != PROPOSAL_REVISION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported proposal revision schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self

    @model_validator(mode="after")
    def validate_selected_option(self) -> ProposalRevisionV1:
        option_ids = {option.option_id for option in self.response_options}
        if self.selected_option_id not in option_ids:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="selectedOptionId must reference a response option",
                details={"selectedOptionId": self.selected_option_id},
            )
        return self


class ApprovalRequirementV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    required: bool
    approver_roles: list[str] = Field(alias="approverRoles", default_factory=list)
    rationale: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ApprovalRequirementV1:
        assert_supported_schema_version("approval_requirement", self.schema_version)
        if self.schema_version != APPROVAL_REQUIREMENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported approval requirement schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class PolicyInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    proposal_revision_id: str = Field(alias="proposalRevisionId", min_length=1, max_length=64)
    proposal_revision_number: int = Field(alias="proposalRevisionNumber", ge=1)
    current_revision_id: str = Field(alias="currentRevisionId", min_length=1, max_length=64)
    action_class: ActionClass = Field(alias="actionClass")
    scenario_command: ScenarioCommandTemplateV1 = Field(alias="scenarioCommand")
    agent_role: AgentRole = Field(alias="agentRole")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    asset_criticality: float = Field(alias="assetCriticality", ge=0.0, le=1.0)
    reversibility: str = Field(min_length=1, max_length=1024)
    incident_state: IncidentState = Field(alias="incidentState")
    scenario_restricted: bool = Field(alias="scenarioRestricted", default=False)
    hypothesis_confidence_min: float | None = Field(
        alias="hypothesisConfidenceMin",
        default=None,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> PolicyInputV1:
        assert_supported_schema_version("policy_input", self.schema_version)
        if self.schema_version != POLICY_INPUT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported policy input schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class PolicyDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    proposal_id: ProposalId = Field(alias="proposalId")
    proposal_revision_id: str = Field(alias="proposalRevisionId", min_length=1, max_length=64)
    incident_id: IncidentId = Field(alias="incidentId")
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId = Field(alias="taskId")
    outcome: PolicyOutcomeV1
    reason_codes: list[PolicyReasonCodeV1] = Field(alias="reasonCodes", min_length=1)
    approval_requirement: ApprovalRequirementV1 | None = Field(
        alias="approvalRequirement",
        default=None,
    )
    policy_input: PolicyInputV1 = Field(alias="policyInput")
    explanation_prose: str = Field(alias="explanationProse", default="", max_length=4096)
    evaluated_at: UtcTimestamp = Field(alias="evaluatedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> PolicyDecisionV1:
        assert_supported_schema_version("policy_decision", self.schema_version)
        if self.schema_version != POLICY_DECISION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported policy decision schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self

    @model_validator(mode="after")
    def validate_approval_requirement(self) -> PolicyDecisionV1:
        if self.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED and self.approval_requirement is None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="approval_required decisions must include approvalRequirement",
                details={"outcome": self.outcome.value},
            )
        return self


class TriggerBastionRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(default="mock", alias="providerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_schema_version(self) -> TriggerBastionRequestV1:
        assert_supported_schema_version("trigger_bastion_request", self.schema_version)
        if self.schema_version != TRIGGER_BASTION_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trigger bastion request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class TriggerWardenRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    proposal_id: ProposalId | None = Field(default=None, alias="proposalId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(default="mock", alias="providerId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_schema_version(self) -> TriggerWardenRequestV1:
        assert_supported_schema_version("trigger_warden_request", self.schema_version)
        if self.schema_version != TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported trigger warden request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
