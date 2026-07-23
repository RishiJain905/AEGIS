"""Phase 7 operator console, direct-action, autonomy and rules-of-engagement contracts.

These model the "2v1": the player acts directly as an operator alongside AI agents that
behave like autonomous teammates. All state-changing operator actions flow through the
same policy → approval → execution pipeline agent proposals use (see
``aegis_api.operator_actions``); nothing here bypasses policy.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import (
    ActionClass,
    AutonomyInitiatorV1,
    RulesOfEngagementV1,
    RunLoadoutV1,
)
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AssetId,
    RunId,
    UtcTimestamp,
)
from aegis_contracts.proposals import PolicyOutcomeV1, ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
    CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION,
    CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION,
    OPERATOR_ACTION_REQUEST_SCHEMA_VERSION,
    OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION,
    OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION,
    ROE_CHANGE_REQUEST_SCHEMA_VERSION,
    RUN_FEED_ENTRY_SCHEMA_VERSION,
    RUN_FEED_PAGE_SCHEMA_VERSION,
    STANDING_DIRECTIVE_SCHEMA_VERSION,
    assert_supported_schema_version,
)

__all__ = [
    "AutonomyInitiatorV1",
    "ConsoleEventSearchRequestV1",
    "ConsoleEventSearchResultV1",
    "ConsoleEventV1",
    "CreateDirectiveRequestV1",
    "OperatorActionRequestV1",
    "OperatorActionResponseV1",
    "OperatorActionStatusV1",
    "OperatorHypothesisRequestV1",
    "RoeChangeRequestV1",
    "RulesOfEngagementV1",
    "RunFeedEntryV1",
    "RunFeedPageV1",
    "RunLoadoutV1",
    "StandingDirectiveV1",
]

MAX_REASON_LENGTH = 2048
MAX_DIRECTIVE_LENGTH = 2048


class OperatorActionRequestV1(BaseModel):
    """Player-initiated containment. Flows through the policy engine exactly like an
    agent proposal; Class 2/3 require ``confirm`` (operator is the incident commander)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scenario_command: ScenarioCommandTemplateV1 = Field(alias="scenarioCommand")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    reason: str = Field(min_length=1, max_length=MAX_REASON_LENGTH)
    # Present + true = the operator has acknowledged the consequences of a Class 2/3
    # action and approves it as the incident commander (approve-and-execute in one call).
    confirm: bool = Field(default=False)
    # Optional: anchor the action to a specific incident. When omitted the service
    # resolves/creates a run-scoped operator incident.
    incident_id: str | None = Field(default=None, alias="incidentId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_schema_version(self) -> OperatorActionRequestV1:
        assert_supported_schema_version("operator_action_request", self.schema_version)
        if self.schema_version != OPERATOR_ACTION_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported operator action request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class OperatorActionStatusV1(StrEnum):
    EXECUTED = "executed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BLOCKED = "blocked"


class OperatorActionResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    proposal_id: str = Field(alias="proposalId")
    incident_id: str = Field(alias="incidentId")
    action_class: ActionClass = Field(alias="actionClass")
    status: OperatorActionStatusV1
    policy_outcome: PolicyOutcomeV1 = Field(alias="policyOutcome")
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")
    executed: bool = False
    executed_action_id: str | None = Field(default=None, alias="executedActionId")
    approval_id: str | None = Field(default=None, alias="approvalId")

    @model_validator(mode="after")
    def validate_schema_version(self) -> OperatorActionResponseV1:
        assert_supported_schema_version("operator_action_response", self.schema_version)
        if self.schema_version != OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported operator action response schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RoeChangeRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    roe: RulesOfEngagementV1

    @model_validator(mode="after")
    def validate_schema_version(self) -> RoeChangeRequestV1:
        assert_supported_schema_version("roe_change_request", self.schema_version)
        if self.schema_version != ROE_CHANGE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported RoE change request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class StandingDirectiveV1(BaseModel):
    """A persistent operator tasking re-evaluated when new matching evidence lands."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    text: str = Field(min_length=1, max_length=MAX_DIRECTIVE_LENGTH)
    scope_asset_ids: list[AssetId] = Field(default_factory=list, alias="scopeAssetIds")
    scope_zone_ids: list[str] = Field(default_factory=list, alias="scopeZoneIds")
    active: bool = True
    created_by: str = Field(alias="createdBy")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> StandingDirectiveV1:
        assert_supported_schema_version("standing_directive", self.schema_version)
        if self.schema_version != STANDING_DIRECTIVE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported standing directive schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CreateDirectiveRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    text: str = Field(min_length=1, max_length=MAX_DIRECTIVE_LENGTH)
    scope_asset_ids: list[AssetId] = Field(default_factory=list, alias="scopeAssetIds")
    scope_zone_ids: list[str] = Field(default_factory=list, alias="scopeZoneIds")

    @model_validator(mode="after")
    def validate_schema_version(self) -> CreateDirectiveRequestV1:
        assert_supported_schema_version("create_directive_request", self.schema_version)
        if self.schema_version != CREATE_DIRECTIVE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported create directive request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ConsoleEventSearchRequestV1(BaseModel):
    """Operator log/event search — the player's read peer to the agents' search_events."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    event_type_prefix: str | None = Field(
        default=None, alias="eventTypePrefix", max_length=128
    )
    text: str | None = Field(default=None, max_length=256)
    from_sim_time: UtcTimestamp | None = Field(default=None, alias="fromSimTime")
    to_sim_time: UtcTimestamp | None = Field(default=None, alias="toSimTime")
    cursor: int | None = Field(default=None, ge=0)
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ConsoleEventSearchRequestV1:
        assert_supported_schema_version("console_event_search_request", self.schema_version)
        if self.schema_version != CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported console event search request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ConsoleEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: str = Field(alias="eventId")
    sequence: int
    type: str
    sim_time: str = Field(alias="simTime")
    asset_id: str | None = Field(default=None, alias="assetId")
    payload: dict[str, Any] = Field(default_factory=dict)


class ConsoleEventSearchResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    events: list[ConsoleEventV1] = Field(default_factory=list)
    count: int = 0
    next_cursor: int | None = Field(default=None, alias="nextCursor")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ConsoleEventSearchResultV1:
        assert_supported_schema_version("console_event_search_result", self.schema_version)
        if self.schema_version != CONSOLE_EVENT_SEARCH_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported console event search result schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class OperatorHypothesisRequestV1(BaseModel):
    """Create an operator-pinned hypothesis, stored alongside agent hypotheses."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    statement: str = Field(min_length=1, max_length=2048)
    asset_ids: list[AssetId] = Field(default_factory=list, alias="assetIds")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    incident_id: str | None = Field(default=None, alias="incidentId")

    @model_validator(mode="after")
    def validate_schema_version(self) -> OperatorHypothesisRequestV1:
        assert_supported_schema_version("operator_hypothesis_request", self.schema_version)
        if self.schema_version != OPERATOR_HYPOTHESIS_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported operator hypothesis request schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RunFeedEntryV1(BaseModel):
    """A single entry in the unified ops feed — a thin projection over the events table."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    sequence: int
    event_id: str = Field(alias="eventId")
    type: str
    category: str
    sim_time: str = Field(alias="simTime")
    initiator: str | None = None
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunFeedEntryV1:
        assert_supported_schema_version("run_feed_entry", self.schema_version)
        if self.schema_version != RUN_FEED_ENTRY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run feed entry schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RunFeedPageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    entries: list[RunFeedEntryV1] = Field(default_factory=list)
    next_cursor: int | None = Field(default=None, alias="nextCursor")

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunFeedPageV1:
        assert_supported_schema_version("run_feed_page", self.schema_version)
        if self.schema_version != RUN_FEED_PAGE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run feed page schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
