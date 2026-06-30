"""Durable persistence-layer contracts for idempotency and object storage references."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import UtcTimestamp
from aegis_contracts.versioning import (
    IDEMPOTENCY_RECORD_SCHEMA_VERSION,
    OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class IdempotencyRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scope: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    request_hash: str | None = Field(default=None, alias="requestHash")
    response_ref: str = Field(alias="responseRef", min_length=1, max_length=512)
    created_at: UtcTimestamp = Field(alias="createdAt")
    replayed: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> IdempotencyRecordV1:
        assert_supported_schema_version("idempotency_record", self.schema_version)
        if self.schema_version != IDEMPOTENCY_RECORD_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported idempotency record schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ObjectMetadataReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    object_key: str = Field(alias="objectKey", min_length=1, max_length=1024)
    checksum: str = Field(min_length=1, max_length=128)
    content_type: str = Field(alias="contentType", min_length=1, max_length=256)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ObjectMetadataReferenceV1:
        assert_supported_schema_version("object_metadata_reference", self.schema_version)
        if self.schema_version != OBJECT_METADATA_REFERENCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported object metadata reference schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self
