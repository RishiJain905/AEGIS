"""Structured contract and API error types."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractErrorCode(StrEnum):
    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    STALE_REVISION = "STALE_REVISION"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"


class ContractValidationError(Exception):
    """Raised when a shared contract fails validation."""

    def __init__(
        self,
        *,
        code: ContractErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        super().__init__(message)

    def to_api_envelope(self) -> dict[str, Any]:
        return ApiErrorEnvelopeV1(
            schema_version=1,
            code=self.code.value,
            message=self.message,
            details=self.details,
            trace_id=self.trace_id,
        ).model_dump(by_alias=True, mode="json")


class ApiErrorEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = Field(default=None, alias="traceId")
