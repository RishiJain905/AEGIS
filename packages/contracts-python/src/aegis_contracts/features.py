"""Phase 14 feature pipeline contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.primitives import (
    AuthoredId,
    EventId,
    RunId,
    Sequence,
    SimTimestamp,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION,
    assert_supported_schema_version,
)

TRANSFORM_VERSION: str = "0.0.0-phase14"
DEFAULT_WINDOW_DURATION_SIM_SECONDS: int = 300


class FeatureErrorCode(StrEnum):
    VALIDATION_FAILED = "FEATURE_VALIDATION_FAILED"
    UNSUPPORTED_EVENT = "FEATURE_UNSUPPORTED_EVENT"
    DUPLICATE_EVENT = "FEATURE_DUPLICATE_EVENT"
    OUT_OF_ORDER = "FEATURE_OUT_OF_ORDER"
    LATE_EVENT = "FEATURE_LATE_EVENT"
    HIDDEN_TRUTH_BLOCKED = "FEATURE_HIDDEN_TRUTH_BLOCKED"
    SCHEMA_MISMATCH = "FEATURE_SCHEMA_MISMATCH"
    MALFORMED_PAYLOAD = "FEATURE_MALFORMED_PAYLOAD"


class FeatureDataType(StrEnum):
    FLOAT = "float"
    INT = "int"
    CATEGORICAL = "categorical"


class FeatureDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1, max_length=128)
    order_index: int = Field(alias="orderIndex", ge=0)
    dtype: FeatureDataType
    unit: str = Field(min_length=1, max_length=64)
    min_value: float | None = Field(default=None, alias="minValue")
    max_value: float | None = Field(default=None, alias="maxValue")
    missing_sentinel: float = Field(alias="missingSentinel")
    categorical_mapping_version: int | None = Field(
        default=None, alias="categoricalMappingVersion", ge=1
    )
    categorical_values: list[str] | None = Field(default=None, alias="categoricalValues")


class FeatureSchemaManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    transform_version: str = Field(alias="transformVersion", min_length=1)
    window_duration_sim_seconds: int = Field(alias="windowDurationSimSeconds", ge=1)
    features: list[FeatureDefinitionV1] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("feature_schema_manifest", value)
        return value

    @model_validator(mode="after")
    def validate_feature_ordering(self) -> FeatureSchemaManifestV1:
        if self.schema_version != FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported feature schema manifest version: {self.schema_version}"
            )
        indices = [feature.order_index for feature in self.features]
        if indices != sorted(indices):
            raise ValueError("Feature definitions must be sorted by orderIndex")
        if len(indices) != len(set(indices)):
            raise ValueError("Feature orderIndex values must be unique")
        return self


class FeatureProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    entity_id: AuthoredId = Field(alias="entityId")
    sequence_start: Sequence = Field(alias="sequenceStart", ge=0)
    sequence_end: Sequence = Field(alias="sequenceEnd", ge=0)
    sim_time_start: SimTimestamp = Field(alias="simTimeStart")
    sim_time_end: SimTimestamp = Field(alias="simTimeEnd")
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    transform_version: str = Field(alias="transformVersion", min_length=1)
    source_event_ids: list[EventId] = Field(alias="sourceEventIds")


class FeatureWindowV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    window_key: str = Field(alias="windowKey", min_length=1)
    run_id: RunId = Field(alias="runId")
    entity_id: AuthoredId = Field(alias="entityId")
    window_start_sim_time: SimTimestamp = Field(alias="windowStartSimTime")
    window_end_sim_time: SimTimestamp = Field(alias="windowEndSimTime")
    is_closed: bool = Field(alias="isClosed")
    watermark_sequence: Sequence = Field(alias="watermarkSequence", ge=0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("feature_window", value)
        return value


class FeatureVectorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    window_key: str = Field(alias="windowKey", min_length=1)
    entity_id: AuthoredId = Field(alias="entityId")
    values: list[float]
    provenance: FeatureProvenanceV1

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("feature_vector", value)
        return value


class DatasetSourceRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    seed: int
    scenario_version_id: AuthoredId = Field(alias="scenarioVersionId")


class DatasetManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    dataset_checksum: str = Field(alias="datasetChecksum", pattern=r"^sha256:[0-9a-f]{64}$")
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    transform_version: str = Field(alias="transformVersion", min_length=1)
    row_count: int = Field(alias="rowCount", ge=0)
    source_runs: list[DatasetSourceRunV1] = Field(alias="sourceRuns", min_length=1)
    window_duration_sim_seconds: int = Field(alias="windowDurationSimSeconds", ge=1)
    created_at: UtcTimestamp = Field(alias="createdAt")
    workspace_version: str = Field(alias="workspaceVersion", min_length=1)
    compatibility_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="compatibilityMetadata"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("dataset_manifest", value)
        return value


class FeatureRejectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: EventId = Field(alias="eventId")
    sequence: Sequence
    code: FeatureErrorCode
    message: str = Field(min_length=1)


class OnlineFeatureUpdateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    window_key: str = Field(alias="windowKey", min_length=1)
    vector: FeatureVectorV1
    last_processed_sequence: Sequence = Field(alias="lastProcessedSequence", ge=0)
    rejections: list[FeatureRejectionV1] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("online_feature_update", value)
        return value


class FeatureComputeRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: Sequence | None = Field(default=None, alias="fromSequence", ge=0)
    to_sequence: Sequence | None = Field(default=None, alias="toSequence", ge=0)
    mode: Literal["incremental", "full"] = "full"


class FeatureComputeResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    vectors: list[FeatureVectorV1]
    windows: list[FeatureWindowV1]
    rejections: list[FeatureRejectionV1]
    last_processed_sequence: Sequence = Field(alias="lastProcessedSequence", ge=0)
    output_checksum: str = Field(alias="outputChecksum", pattern=r"^sha256:[0-9a-f]{64}$")


class FeatureParityCheckResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    matching: bool
    offline_checksum: str = Field(alias="offlineChecksum", pattern=r"^sha256:[0-9a-f]{64}$")
    online_checksum: str = Field(alias="onlineChecksum", pattern=r"^sha256:[0-9a-f]{64}$")
    vector_count: int = Field(alias="vectorCount", ge=0)
    rejection_count: int = Field(alias="rejectionCount", ge=0)
