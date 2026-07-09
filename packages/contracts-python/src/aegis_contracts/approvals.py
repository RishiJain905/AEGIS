"""Phase 24 approval workflow contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import ApprovalV1, ExecutedActionV1, ProposalStatus
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    ApprovalId,
    EventId,
    ProposalId,
    Revision,
    RunId,
    UtcTimestamp,
)
from aegis_contracts.proposals import (
    PolicyDecisionV1,
    PolicyOutcomeV1,
    ResponseOptionV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import (
    APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
    APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION,
    CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION,
    EXECUTION_RESULT_SCHEMA_VERSION,
    FINAL_POLICY_CHECK_SCHEMA_VERSION,
    MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION,
    MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    PROPOSAL_MODIFICATION_SCHEMA_VERSION,
    REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION,
    REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    STALE_PROPOSAL_ERROR_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ApprovalErrorCode(StrEnum):
    STALE_PROPOSAL = "STALE_PROPOSAL"
    UNAUTHORIZED = "UNAUTHORIZED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_DECIDED = "ALREADY_DECIDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class StaleProposalErrorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    code: ApprovalErrorCode = Field(default=ApprovalErrorCode.STALE_PROPOSAL)
    message: str = Field(min_length=1, max_length=1024)
    proposal_id: ProposalId = Field(alias="proposalId")
    expected_revision_id: str | None = Field(default=None, alias="expectedRevisionId")
    actual_revision_id: str | None = Field(default=None, alias="actualRevisionId")
    expected_revision: Revision | None = Field(default=None, alias="expectedRevision")
    actual_revision: Revision | None = Field(default=None, alias="actualRevision")
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> StaleProposalErrorV1:
        assert_supported_schema_version("stale_proposal_error", self.schema_version)
        if self.schema_version != STALE_PROPOSAL_ERROR_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported stale proposal error schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ProposalModificationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    previous_revision_id: str = Field(alias="previousRevisionId", min_length=1, max_length=64)
    new_revision_id: str = Field(alias="newRevisionId", min_length=1, max_length=64)
    selected_option_id: str = Field(alias="selectedOptionId", min_length=1, max_length=64)
    response_options: list[ResponseOptionV1] | None = Field(
        default=None,
        alias="responseOptions",
    )
    rationale: str = Field(min_length=1, max_length=4096)
    risk_tradeoffs: str = Field(alias="riskTradeoffs", min_length=1, max_length=4096)
    comment: str = Field(default="", max_length=2048)
    modified_by: str = Field(alias="modifiedBy", min_length=1, max_length=128)
    modified_at: UtcTimestamp = Field(alias="modifiedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ProposalModificationV1:
        assert_supported_schema_version("proposal_modification", self.schema_version)
        if self.schema_version != PROPOSAL_MODIFICATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported proposal modification schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class FinalPolicyCheckV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    proposal_revision_id: str = Field(alias="proposalRevisionId", min_length=1, max_length=64)
    current_revision_id: str = Field(alias="currentRevisionId", min_length=1, max_length=64)
    outcome: PolicyOutcomeV1
    decision: PolicyDecisionV1
    executable: bool
    checked_at: UtcTimestamp = Field(alias="checkedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> FinalPolicyCheckV1:
        assert_supported_schema_version("final_policy_check", self.schema_version)
        if self.schema_version != FINAL_POLICY_CHECK_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported final policy check schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AuthorizedSimulationCommandV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    approval_id: ApprovalId = Field(alias="approvalId")
    run_id: RunId = Field(alias="runId")
    scenario_command: ScenarioCommandTemplateV1 = Field(alias="scenarioCommand")
    plugin_id: str = Field(alias="pluginId", min_length=1, max_length=128)
    target_asset_id: str = Field(alias="targetAssetId", min_length=1, max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)
    command_id: str = Field(alias="commandId", min_length=1, max_length=256)
    authorization_token: str = Field(alias="authorizationToken", min_length=1, max_length=256)
    actor_id: str = Field(alias="actorId", min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> AuthorizedSimulationCommandV1:
        assert_supported_schema_version("authorized_simulation_command", self.schema_version)
        if self.schema_version != AUTHORIZED_SIMULATION_COMMAND_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported authorized simulation command schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ExecutionResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    executed_action: ExecutedActionV1 = Field(alias="executedAction")
    result_event_id: EventId = Field(alias="resultEventId")
    command_id: str = Field(alias="commandId", min_length=1, max_length=256)
    success: bool
    replayed: bool = False
    message: str = Field(default="", max_length=1024)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ExecutionResultV1:
        assert_supported_schema_version("execution_result", self.schema_version)
        if self.schema_version != EXECUTION_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported execution result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ApproveProposalRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    expected_revision_id: str = Field(alias="expectedRevisionId", min_length=1, max_length=64)
    expected_revision: Revision = Field(alias="expectedRevision")
    comment: str = Field(default="", max_length=2048)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ApproveProposalRequestV1:
        assert_supported_schema_version("approve_proposal_request", self.schema_version)
        if self.schema_version != APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported approve proposal request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RejectProposalRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    expected_revision_id: str = Field(alias="expectedRevisionId", min_length=1, max_length=64)
    expected_revision: Revision = Field(alias="expectedRevision")
    reason: str = Field(min_length=1, max_length=2048)
    comment: str = Field(default="", max_length=2048)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> RejectProposalRequestV1:
        assert_supported_schema_version("reject_proposal_request", self.schema_version)
        if self.schema_version != REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported reject proposal request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModifyProposalRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    expected_revision_id: str = Field(alias="expectedRevisionId", min_length=1, max_length=64)
    expected_revision: Revision = Field(alias="expectedRevision")
    selected_option_id: str = Field(alias="selectedOptionId", min_length=1, max_length=64)
    response_options: list[ResponseOptionV1] | None = Field(
        default=None,
        alias="responseOptions",
    )
    rationale: str = Field(min_length=1, max_length=4096)
    risk_tradeoffs: str = Field(alias="riskTradeoffs", min_length=1, max_length=4096)
    comment: str = Field(default="", max_length=2048)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ModifyProposalRequestV1:
        assert_supported_schema_version("modify_proposal_request", self.schema_version)
        if self.schema_version != MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported modify proposal request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CancelProposalRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: ProposalId = Field(alias="proposalId")
    expected_revision_id: str = Field(alias="expectedRevisionId", min_length=1, max_length=64)
    expected_revision: Revision = Field(alias="expectedRevision")
    reason: str = Field(min_length=1, max_length=2048)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    actor_id: str | None = Field(default=None, alias="actorId", max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> CancelProposalRequestV1:
        assert_supported_schema_version("cancel_proposal_request", self.schema_version)
        if self.schema_version != CANCEL_PROPOSAL_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported cancel proposal request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ApproveProposalResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    approval: ApprovalV1
    final_policy_check: FinalPolicyCheckV1 = Field(alias="finalPolicyCheck")
    execution: ExecutionResultV1 | None = None
    proposal_status: ProposalStatus = Field(alias="proposalStatus")
    replayed: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> ApproveProposalResponseV1:
        assert_supported_schema_version("approve_proposal_response", self.schema_version)
        if self.schema_version != APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported approve proposal response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RejectProposalResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    approval: ApprovalV1
    proposal_status: ProposalStatus = Field(alias="proposalStatus")
    replayed: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> RejectProposalResponseV1:
        assert_supported_schema_version("reject_proposal_response", self.schema_version)
        if self.schema_version != REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported reject proposal response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModifyProposalResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    modification: ProposalModificationV1
    policy_decision: PolicyDecisionV1 = Field(alias="policyDecision")
    proposal_status: ProposalStatus = Field(alias="proposalStatus")
    replayed: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> ModifyProposalResponseV1:
        assert_supported_schema_version("modify_proposal_response", self.schema_version)
        if self.schema_version != MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported modify proposal response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


__all__ = [
    "ApprovalErrorCode",
    "ApproveProposalRequestV1",
    "ApproveProposalResponseV1",
    "AuthorizedSimulationCommandV1",
    "CancelProposalRequestV1",
    "ExecutionResultV1",
    "FinalPolicyCheckV1",
    "ModifyProposalRequestV1",
    "ModifyProposalResponseV1",
    "ProposalModificationV1",
    "RejectProposalRequestV1",
    "RejectProposalResponseV1",
    "StaleProposalErrorV1",
]
