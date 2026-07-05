"""Phase 18 model-provider generation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import CorrelationId, GenerationRequestId, TraceId, UtcTimestamp
from aegis_contracts.versioning import (
    assert_supported_schema_version,
)


class GenerationMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ProviderCapability(StrEnum):
    STRUCTURED_OUTPUT = "structured_output"
    TOOLS = "tools"
    VISION = "vision"
    STREAMING = "streaming"


class ProviderFinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class ProviderErrorCode(StrEnum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"
    TIMEOUT = "TIMEOUT"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    CANCELLATION = "CANCELLATION"
    INTERNAL = "INTERNAL"


class GenerationMessageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    role: GenerationMessageRole
    content: str = Field(min_length=0, max_length=65536)
    name: str | None = Field(default=None, max_length=128)


class ToolSchemaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2048)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("tool_schema", value)
        return value


class StructuredOutputSpecV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    json_schema: dict[str, Any] = Field(alias="jsonSchema")
    strict: bool = True
    max_repair_attempts: int = Field(alias="maxRepairAttempts", ge=0, le=2, default=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("structured_output_spec", value)
        return value


class ProviderCapabilitiesV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    capabilities: list[ProviderCapability] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("provider_capabilities", value)
        return value


class ModelConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    prompt_version: str = Field(alias="promptVersion", min_length=1, max_length=64)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, alias="maxOutputTokens", ge=1, le=65536)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_config", value)
        return value


class ProviderUsageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    prompt_tokens: int = Field(alias="promptTokens", ge=0)
    completion_tokens: int = Field(alias="completionTokens", ge=0)
    total_tokens: int = Field(alias="totalTokens", ge=0)
    estimated_cost_usd: float | None = Field(default=None, alias="estimatedCostUsd", ge=0.0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("provider_usage", value)
        return value

    @model_validator(mode="after")
    def validate_totals(self) -> ProviderUsageV1:
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="totalTokens must equal promptTokens + completionTokens",
                details={
                    "promptTokens": self.prompt_tokens,
                    "completionTokens": self.completion_tokens,
                    "totalTokens": self.total_tokens,
                },
            )
        return self


class ProviderErrorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    code: ProviderErrorCode
    message: str = Field(min_length=1, max_length=2048)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: TraceId | None = Field(default=None, alias="traceId")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("provider_error", value)
        return value


class RecordedResponseKeyV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    prompt_version: str = Field(alias="promptVersion", min_length=1, max_length=64)
    request_hash: str = Field(alias="requestHash", min_length=8, max_length=128)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("recorded_response_key", value)
        return value


class GenerationRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    request_id: GenerationRequestId = Field(alias="requestId")
    trace_id: TraceId = Field(alias="traceId")
    correlation_id: CorrelationId | None = Field(default=None, alias="correlationId")
    provider_id: str | None = Field(default=None, alias="providerId", max_length=64)
    model_config_ref: ModelConfigV1 = Field(alias="modelConfig")
    messages: list[GenerationMessageV1] = Field(min_length=1, max_length=64)
    tools: list[ToolSchemaV1] = Field(default_factory=list, max_length=32)
    structured_output: StructuredOutputSpecV1 | None = Field(
        default=None, alias="structuredOutput"
    )
    capabilities_required: list[ProviderCapability] = Field(
        default_factory=list, alias="capabilitiesRequired"
    )
    max_output_tokens: int = Field(alias="maxOutputTokens", ge=1, le=65536, default=4096)
    timeout_ms: int | None = Field(default=None, alias="timeoutMs", ge=100, le=600000)
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey", max_length=256)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("generation_request", value)
        return value


class GenerationResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    request_id: GenerationRequestId = Field(alias="requestId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    prompt_version: str = Field(alias="promptVersion", min_length=1, max_length=64)
    content: str | None = Field(default=None, max_length=65536)
    structured_data: dict[str, Any] | None = Field(default=None, alias="structuredData")
    finish_reason: ProviderFinishReason = Field(alias="finishReason")
    usage: ProviderUsageV1
    latency_ms: int = Field(alias="latencyMs", ge=0)
    artifact_ref: str | None = Field(default=None, alias="artifactRef", max_length=512)
    completed_at: UtcTimestamp = Field(alias="completedAt")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("generation_response", value)
        return value


class GenerationArtifactV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    request_id: GenerationRequestId = Field(alias="requestId")
    trace_id: TraceId = Field(alias="traceId")
    provider_id: str = Field(alias="providerId", min_length=1, max_length=64)
    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    prompt_version: str = Field(alias="promptVersion", min_length=1, max_length=64)
    latency_ms: int = Field(alias="latencyMs", ge=0)
    usage: ProviderUsageV1 | None = None
    error: ProviderErrorV1 | None = None
    sanitized_request: dict[str, Any] = Field(alias="sanitizedRequest")
    sanitized_response: dict[str, Any] | None = Field(default=None, alias="sanitizedResponse")
    object_storage_ref: str | None = Field(default=None, alias="objectStorageRef", max_length=512)
    recorded_at: UtcTimestamp = Field(alias="recordedAt")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("generation_artifact", value)
        return value


class ProviderGenerateRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    request: GenerationRequestV1
    provider_id: str | None = Field(default=None, alias="providerId", max_length=64)
    dry_run: bool = Field(default=False, alias="dryRun")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("provider_generate_request", value)
        return value


class ProviderGenerateResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    response: GenerationResponseV1 | None = None
    error: ProviderErrorV1 | None = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("provider_generate_response", value)
        return value

    @model_validator(mode="after")
    def validate_result(self) -> ProviderGenerateResponseV1:
        if (self.response is None) == (self.error is None):
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Exactly one of response or error must be set",
            )
        return self
