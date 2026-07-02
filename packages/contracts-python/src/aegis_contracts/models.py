"""Phase 16 anomaly model contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import AssetId, EventId, ModelId, RunId, SimTimestamp, UtcTimestamp
from aegis_contracts.versioning import (
    ANOMALY_EXPLANATION_SCHEMA_VERSION,
    MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION,
    MODEL_EVALUATE_REQUEST_SCHEMA_VERSION,
    MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION,
    MODEL_INFERENCE_RESULT_SCHEMA_VERSION,
    MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION,
    MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
    TRAINING_RUN_MANIFEST_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class ModelApprovalStatus(StrEnum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class AnomalyRiskBand(StrEnum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"


class SourceWindowV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    window_start_epoch: int = Field(alias="windowStartEpoch", ge=0)
    window_end_epoch: int = Field(alias="windowEndEpoch", ge=0)
    sim_time_start: SimTimestamp = Field(alias="simTimeStart")
    sim_time_end: SimTimestamp = Field(alias="simTimeEnd")


class BaselineComparisonV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    baseline_version: str = Field(alias="baselineVersion", min_length=1)
    feature_name: str = Field(alias="featureName", min_length=1)
    observed_value: float = Field(alias="observedValue")
    baseline_mean: float = Field(alias="baselineMean")
    baseline_std: float = Field(alias="baselineStd", ge=0.0)
    z_score: float = Field(alias="zScore")


class AnomalyExplanationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    summary: str = Field(min_length=1)
    top_features: list[str] = Field(alias="topFeatures", min_length=1)
    feature_contributions: dict[str, float] = Field(alias="featureContributions")
    threshold: float = Field(ge=0.0, le=1.0)
    observed_score: float = Field(alias="observedScore", ge=0.0, le=1.0)
    source_window: SourceWindowV1 = Field(alias="sourceWindow")
    model_version_id: ModelId = Field(alias="modelVersionId")
    model_semantic_version: str = Field(alias="modelSemanticVersion", min_length=1)
    comparison_baseline: BaselineComparisonV1 | None = Field(
        default=None,
        alias="comparisonBaseline",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("anomaly_explanation", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> AnomalyExplanationV1:
        if self.schema_version != ANOMALY_EXPLANATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported anomaly explanation schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelArtifactReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    object_key: str = Field(alias="objectKey", min_length=1, max_length=1024)
    checksum: str = Field(min_length=1, max_length=128)
    content_type: str = Field(alias="contentType", min_length=1, max_length=256)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    serialization_format: str = Field(alias="serializationFormat", min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_artifact_reference", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelArtifactReferenceV1:
        if self.schema_version != MODEL_ARTIFACT_REFERENCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported model artifact reference schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class TrainingRunManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    training_run_id: str = Field(alias="trainingRunId", min_length=1)
    scenario_id: str = Field(alias="scenarioId", min_length=1)
    training_seeds: list[int] = Field(alias="trainingSeeds", min_length=1)
    holdout_seeds: list[int] = Field(alias="holdoutSeeds", min_length=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    dataset_ids: list[str] = Field(alias="datasetIds", default_factory=list)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int = Field(alias="randomSeed", ge=0)
    code_revision: str = Field(alias="codeRevision", min_length=1)
    sklearn_version: str = Field(alias="sklearnVersion", min_length=1)
    vector_count: int = Field(alias="vectorCount", ge=0)
    split_policy: str = Field(alias="splitPolicy", min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("training_run_manifest", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> TrainingRunManifestV1:
        if self.schema_version != TRAINING_RUN_MANIFEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported training run manifest schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskBandThresholdsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    elevated: float = Field(ge=0.0, le=1.0)
    high: float = Field(ge=0.0, le=1.0)


class ModelInferenceResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    entity_id: AssetId = Field(alias="entityId")
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    risk_band: AnomalyRiskBand = Field(alias="riskBand")
    explanation: AnomalyExplanationV1
    deduplication_key: str = Field(alias="deduplicationKey", min_length=1)
    source_event_id: EventId | None = Field(default=None, alias="sourceEventId")
    is_anomaly: bool = Field(alias="isAnomaly")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_inference_result", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelInferenceResultV1:
        if self.schema_version != MODEL_INFERENCE_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported model inference result schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelScoreRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: int | None = Field(default=None, alias="fromSequence", ge=1)
    to_sequence: int | None = Field(default=None, alias="toSequence", ge=1)
    dry_run: bool = Field(default=False, alias="dryRun")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_evaluate_request", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelScoreRequestV1:
        if self.schema_version != MODEL_EVALUATE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported model evaluate request schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelScoreResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    model_version_id: ModelId | None = Field(default=None, alias="modelVersionId")
    scores_computed: int = Field(alias="scoresComputed", ge=0)
    anomalies_detected: int = Field(alias="anomaliesDetected", ge=0)
    alerts_persisted: int = Field(alias="alertsPersisted", ge=0)
    scores_suppressed: int = Field(alias="scoresSuppressed", ge=0)
    fallback_active: bool = Field(alias="fallbackActive")
    fallback_reason: str | None = Field(default=None, alias="fallbackReason")
    results: list[ModelInferenceResultV1] = Field(default_factory=list)
    deterministic_checksum: str = Field(alias="deterministicChecksum", min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_evaluate_response", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelScoreResponseV1:
        if self.schema_version != MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported model evaluate response schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelVerifyArtifactRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    manifest_path: str = Field(alias="manifestPath", min_length=1)
    artifact_path: str | None = Field(default=None, alias="artifactPath")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_verify_artifact_request", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelVerifyArtifactRequestV1:
        if self.schema_version != MODEL_VERIFY_ARTIFACT_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported model verify artifact request schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self


class ModelVerifyArtifactResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    valid: bool
    checksum_match: bool = Field(alias="checksumMatch")
    schema_compatible: bool = Field(alias="schemaCompatible")
    approval_status: ModelApprovalStatus | None = Field(
        default=None,
        alias="approvalStatus",
    )
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("model_verify_artifact_response", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> ModelVerifyArtifactResponseV1:
        if self.schema_version != MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported model verify artifact response schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self
