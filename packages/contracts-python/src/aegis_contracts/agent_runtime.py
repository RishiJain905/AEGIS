"""Phase 19 agent runtime contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import AgentRole, AgentSessionState, AgentSessionV1
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AgentArtifactId,
    AgentSessionId,
    AgentTaskId,
    EvidenceId,
    GenerationRequestId,
    IncidentId,
    RunId,
    ToolInvocationId,
    TraceId,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    AGENT_ARTIFACT_SCHEMA_VERSION,
    AGENT_BUDGET_SCHEMA_VERSION,
    AGENT_DEFINITION_SCHEMA_VERSION,
    AGENT_SESSION_DETAIL_SCHEMA_VERSION,
    AGENT_STATE_TRANSITION_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
    EVIDENCE_CITATION_SCHEMA_VERSION,
    TOOL_DEFINITION_SCHEMA_VERSION,
    TOOL_INVOCATION_SCHEMA_VERSION,
    TOOL_RESULT_SCHEMA_VERSION,
    assert_supported_schema_version,
)

# Upper bound on the operator free-text directive threaded into a task prompt.
# Bounded so an untrusted instruction cannot blow the prompt/token budget.
MAX_OPERATOR_INSTRUCTIONS_LENGTH = 4000


class AgentTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AgentToolClass(StrEnum):
    READ = "read"
    ANALYSIS_WRITE = "analysis_write"
    PROPOSAL = "proposal"
    EXECUTION = "execution"


class ToolInvocationStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


class AgentArtifactType(StrEnum):
    STEP_RESULT = "step_result"
    HYPOTHESIS = "hypothesis"
    PROPOSAL = "proposal"
    AUDIT = "audit"


class AgentBudgetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    max_tokens: int = Field(alias="maxTokens", ge=1)
    max_latency_ms: int = Field(alias="maxLatencyMs", ge=1)
    max_cost_usd: float = Field(alias="maxCostUsd", ge=0.0)
    consumed_tokens: int = Field(alias="consumedTokens", ge=0, default=0)
    consumed_latency_ms: int = Field(alias="consumedLatencyMs", ge=0, default=0)
    consumed_cost_usd: float = Field(alias="consumedCostUsd", ge=0.0, default=0.0)

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentBudgetV1:
        assert_supported_schema_version("agent_budget", self.schema_version)
        if self.schema_version != AGENT_BUDGET_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent budget schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    role: AgentRole
    definition_id: str = Field(alias="definitionId", min_length=1, max_length=128)
    prompt_version: str = Field(alias="promptVersion", min_length=1, max_length=64)
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    allowed_tools: list[str] = Field(alias="allowedTools")
    default_budget: AgentBudgetV1 = Field(alias="defaultBudget")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentDefinitionV1:
        assert_supported_schema_version("agent_definition", self.schema_version)
        if self.schema_version != AGENT_DEFINITION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent definition schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ToolDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2048)
    tool_class: AgentToolClass = Field(alias="toolClass")
    model_visible: bool = Field(alias="modelVisible")
    input_schema: dict[str, Any] = Field(alias="inputSchema", default_factory=dict)
    output_schema: dict[str, Any] = Field(alias="outputSchema", default_factory=dict)
    allowed_roles: list[AgentRole] = Field(alias="allowedRoles")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ToolDefinitionV1:
        assert_supported_schema_version("tool_definition", self.schema_version)
        if self.schema_version != TOOL_DEFINITION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported tool definition schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.tool_class == AgentToolClass.EXECUTION and self.model_visible:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Execution-class tools must not be model-visible",
                details={"name": self.name},
            )
        return self


class EvidenceCitationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    evidence_id: EvidenceId = Field(alias="evidenceId")
    rationale: str = ""

    @model_validator(mode="after")
    def validate_schema_version(self) -> EvidenceCitationV1:
        assert_supported_schema_version("evidence_citation", self.schema_version)
        if self.schema_version != EVIDENCE_CITATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported evidence citation schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentTaskV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AgentTaskId
    session_id: AgentSessionId = Field(alias="sessionId")
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    status: AgentTaskStatus
    attempt: int = Field(ge=1, default=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    # Operator free-text directive that steered this task, retained so the chat
    # thread can be restored from task history. Untrusted; never authoritative.
    instructions: str | None = Field(
        default=None, max_length=MAX_OPERATOR_INSTRUCTIONS_LENGTH
    )
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")
    started_at: UtcTimestamp | None = Field(default=None, alias="startedAt")
    completed_at: UtcTimestamp | None = Field(default=None, alias="completedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentTaskV1:
        assert_supported_schema_version("agent_task", self.schema_version)
        if self.schema_version != AGENT_TASK_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent task schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentStateTransitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1, max_length=64)
    session_id: AgentSessionId = Field(alias="sessionId")
    task_id: AgentTaskId | None = Field(default=None, alias="taskId")
    from_state: AgentSessionState = Field(alias="fromState")
    to_state: AgentSessionState = Field(alias="toState")
    reason: str = Field(min_length=1, max_length=512)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentStateTransitionV1:
        assert_supported_schema_version("agent_state_transition", self.schema_version)
        if self.schema_version != AGENT_STATE_TRANSITION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent state transition schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ToolInvocationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ToolInvocationId
    task_id: AgentTaskId = Field(alias="taskId")
    session_id: AgentSessionId = Field(alias="sessionId")
    tool_name: str = Field(alias="toolName", min_length=1, max_length=128)
    tool_class: AgentToolClass = Field(alias="toolClass")
    status: ToolInvocationStatus
    duration_ms: int = Field(alias="durationMs", ge=0)
    input_payload: dict[str, Any] = Field(alias="input", default_factory=dict)
    output_payload: dict[str, Any] | None = Field(default=None, alias="output")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ToolInvocationV1:
        assert_supported_schema_version("tool_invocation", self.schema_version)
        if self.schema_version != TOOL_INVOCATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported tool invocation schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ToolResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    invocation_id: ToolInvocationId = Field(alias="invocationId")
    status: ToolInvocationStatus
    output: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ToolResultV1:
        assert_supported_schema_version("tool_result", self.schema_version)
        if self.schema_version != TOOL_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported tool result schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentArtifactV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AgentArtifactId
    task_id: AgentTaskId = Field(alias="taskId")
    session_id: AgentSessionId = Field(alias="sessionId")
    artifact_type: AgentArtifactType = Field(alias="artifactType")
    payload: dict[str, Any] = Field(default_factory=dict)
    generation_artifact_id: GenerationRequestId | None = Field(
        default=None, alias="generationArtifactId"
    )
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentArtifactV1:
        assert_supported_schema_version("agent_artifact", self.schema_version)
        if self.schema_version != AGENT_ARTIFACT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent artifact schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class CreateAgentSessionRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    role: AgentRole
    trace_id: TraceId = Field(alias="traceId")
    enqueue_initial_task: bool = Field(alias="enqueueInitialTask", default=True)
    provider_id: str | None = Field(default=None, alias="providerId")
    # Optional operator directive applied to the auto-enqueued initial task, so a
    # run-scoped session can open with the player's first message in one call.
    instructions: str | None = Field(
        default=None, max_length=MAX_OPERATOR_INSTRUCTIONS_LENGTH
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> CreateAgentSessionRequestV1:
        assert_supported_schema_version("create_agent_session_request", self.schema_version)
        if self.schema_version != CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported create agent session request schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class CreateAgentTaskRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    provider_id: str | None = Field(default=None, alias="providerId")
    # Operator free-text directive for this task (the chat composer message).
    instructions: str | None = Field(
        default=None, max_length=MAX_OPERATOR_INSTRUCTIONS_LENGTH
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> CreateAgentTaskRequestV1:
        assert_supported_schema_version("create_agent_task_request", self.schema_version)
        if self.schema_version != CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported create agent task request schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class AgentSessionDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    session: AgentSessionV1
    tasks: list[AgentTaskV1] = Field(default_factory=list)
    transitions: list[AgentStateTransitionV1] = Field(default_factory=list)
    tool_invocations: list[ToolInvocationV1] = Field(alias="toolInvocations", default_factory=list)
    artifacts: list[AgentArtifactV1] = Field(default_factory=list)
    budget: AgentBudgetV1 | None = None

    @model_validator(mode="after")
    def validate_schema_version(self) -> AgentSessionDetailV1:
        assert_supported_schema_version("agent_session_detail", self.schema_version)
        if self.schema_version != AGENT_SESSION_DETAIL_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported agent session detail schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
