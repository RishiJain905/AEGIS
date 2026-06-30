"""API protocol contracts: pagination, idempotency, and versioning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.versioning import (
    CURSOR_PAGINATION_SCHEMA_VERSION,
    IDEMPOTENCY_SCHEMA_VERSION,
    PROTOCOL_VERSION_V1,
    assert_supported_schema_version,
)


class ProtocolVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    major: int = Field(ge=1)
    minor: int = Field(ge=0)

    @property
    def header_value(self) -> str:
        return f"{self.major}.{self.minor}"


PROTOCOL_VERSION = ProtocolVersion(major=PROTOCOL_VERSION_V1, minor=0)


class CursorPaginationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    cursor: str | None = None
    limit: int = Field(ge=1, le=1000, default=100)
    has_more: bool = Field(alias="hasMore")
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    @model_validator(mode="after")
    def validate_schema_version(self) -> CursorPaginationV1:
        assert_supported_schema_version("cursor_pagination", self.schema_version)
        if self.schema_version != CURSOR_PAGINATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported cursor pagination schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class IdempotencyMetadataV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    request_hash: str | None = Field(default=None, alias="requestHash")
    replayed: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> IdempotencyMetadataV1:
        assert_supported_schema_version("idempotency", self.schema_version)
        if self.schema_version != IDEMPOTENCY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported idempotency schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
