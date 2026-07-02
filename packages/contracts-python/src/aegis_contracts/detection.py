"""Phase 15 detection rule and baseline contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AssetId,
    AuthoredId,
    EventId,
    RunId,
    SimTimestamp,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    DETECTION_RULE_SCHEMA_VERSION,
    RULE_THRESHOLD_SCHEMA_VERSION,
    assert_supported_schema_version,
)

RULE_REGISTRY_VERSION: str = "1.0.0"
BASELINE_VERSION: str = "1.0.0"
THRESHOLD_CONFIG_VERSION: str = "1.0.0"


class DetectorType(StrEnum):
    DETERMINISTIC = "deterministic"
    STATISTICAL_BASELINE = "statistical_baseline"


class ThresholdOperator(StrEnum):
    GTE = "gte"
    GT = "gt"
    LTE = "lte"
    LT = "lt"
    EQ = "eq"


class BaselineMethod(StrEnum):
    ROLLING_MEAN_STD = "rolling_mean_std"


class RuleEvaluationStatus(StrEnum):
    FIRED = "fired"
    SKIPPED = "skipped"
    ERROR = "error"


class RuleThresholdV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    feature_name: str = Field(alias="featureName", min_length=1)
    operator: ThresholdOperator
    value: float
    min_count: float | None = Field(default=None, alias="minCount")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("rule_threshold", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RuleThresholdV1:
        if self.schema_version != RULE_THRESHOLD_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported rule threshold schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class DetectionRuleV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    rule_id: str = Field(alias="ruleId", min_length=1)
    rule_version: str = Field(alias="ruleVersion", min_length=1)
    detector_type: DetectorType = Field(alias="detectorType")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_features: list[str] = Field(alias="inputFeatures", min_length=1)
    thresholds: list[RuleThresholdV1] = Field(min_length=1)
    severity: str = Field(min_length=1)
    confidence_base: float = Field(alias="confidenceBase", ge=0.0, le=1.0)
    cooldown_sim_seconds: int = Field(alias="cooldownSimSeconds", ge=0)
    suppression_group: str | None = Field(default=None, alias="suppressionGroup")
    enabled: bool = True

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("detection_rule", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> DetectionRuleV1:
        if self.schema_version != DETECTION_RULE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported detection rule schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class DetectionRuleRegistryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    registry_version: str = Field(alias="registryVersion", min_length=1)
    threshold_config_version: str = Field(alias="thresholdConfigVersion", min_length=1)
    rules: list[DetectionRuleV1] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("detection_rule_registry", value)
        return value


class StatisticalBaselineEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_name: str = Field(alias="featureName", min_length=1)
    entity_id: AuthoredId | None = Field(default=None, alias="entityId")
    mean: float
    std: float
    sample_count: int = Field(alias="sampleCount", ge=0)
    z_score_threshold: float = Field(alias="zScoreThreshold", ge=0.0)


class StatisticalBaselineV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    baseline_version: str = Field(alias="baselineVersion", min_length=1)
    method: BaselineMethod
    training_seeds: list[int] = Field(alias="trainingSeeds", min_length=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    entries: list[StatisticalBaselineEntryV1] = Field(min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("statistical_baseline", value)
        return value


class StatisticalBaselineManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    baseline_version: str = Field(alias="baselineVersion", min_length=1)
    baseline_checksum: str = Field(alias="baselineChecksum", pattern=r"^sha256:[0-9a-f]{64}$")
    training_seeds: list[int] = Field(alias="trainingSeeds", min_length=1)
    holdout_seeds: list[int] = Field(alias="holdoutSeeds", min_length=1)
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    workspace_version: str = Field(alias="workspaceVersion", min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("statistical_baseline_manifest", value)
        return value


class RuleExplanationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    summary: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    feature_name: str = Field(alias="featureName", min_length=1)
    observed: float
    baseline: float | None = None
    threshold: float
    comparison: str = Field(min_length=1)
    window_key: str = Field(alias="windowKey", min_length=1)
    detector_type: DetectorType = Field(alias="detectorType")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("rule_explanation", value)
        return value


class AlertEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    feature_values: dict[str, float] = Field(alias="featureValues")
    source_event_ids: list[EventId] = Field(alias="sourceEventIds")
    window_key: str = Field(alias="windowKey", min_length=1)
    sequence_start: int = Field(alias="sequenceStart", ge=0)
    sequence_end: int = Field(alias="sequenceEnd", ge=0)
    sim_time_start: SimTimestamp = Field(alias="simTimeStart")
    sim_time_end: SimTimestamp = Field(alias="simTimeEnd")


class AlertCandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    rule_id: str = Field(alias="ruleId", min_length=1)
    rule_version: str = Field(alias="ruleVersion", min_length=1)
    detector_id: str = Field(alias="detectorId", min_length=1)
    detector_version: str = Field(alias="detectorVersion", min_length=1)
    detector_type: DetectorType = Field(alias="detectorType")
    entity_id: AssetId = Field(alias="entityId")
    title: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    observed_value: float = Field(alias="observedValue")
    baseline_value: float | None = Field(default=None, alias="baselineValue")
    threshold: float
    source_window_key: str = Field(alias="sourceWindowKey", min_length=1)
    deduplication_key: str = Field(alias="deduplicationKey", min_length=1)
    explanation: RuleExplanationV1
    evidence: AlertEvidenceV1
    source_event_id: EventId = Field(alias="sourceEventId")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("alert_candidate", value)
        return value


class RuleEvaluationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    rule_id: str = Field(alias="ruleId", min_length=1)
    status: RuleEvaluationStatus
    candidate: AlertCandidateV1 | None = None
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("rule_evaluation", value)
        return value


class EvaluationSeedMetricsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    seed: int
    run_id: RunId | None = Field(default=None, alias="runId")
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    false_positive_rate: float = Field(alias="falsePositiveRate", ge=0.0, le=1.0)
    detection_delay_sim_seconds: float | None = Field(
        default=None, alias="detectionDelaySimSeconds", ge=0.0
    )
    cause_coverage: float = Field(alias="causeCoverage", ge=0.0, le=1.0)
    true_positives: int = Field(alias="truePositives", ge=0)
    false_positives: int = Field(alias="falsePositives", ge=0)
    false_negatives: int = Field(alias="falseNegatives", ge=0)


class MetricReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    false_positive_rate: float = Field(alias="falsePositiveRate", ge=0.0, le=1.0)
    mean_detection_delay_sim_seconds: float | None = Field(
        default=None, alias="meanDetectionDelaySimSeconds", ge=0.0
    )
    cause_coverage: float = Field(alias="causeCoverage", ge=0.0, le=1.0)
    per_seed: list[EvaluationSeedMetricsV1] = Field(alias="perSeed", min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("metric_report", value)
        return value


class EvaluationRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    evaluation_id: str = Field(alias="evaluationId", min_length=1)
    scenario_id: str = Field(alias="scenarioId", min_length=1)
    training_seeds: list[int] = Field(alias="trainingSeeds", min_length=1)
    holdout_seeds: list[int] = Field(alias="holdoutSeeds", min_length=1)
    rule_registry_version: str = Field(alias="ruleRegistryVersion", min_length=1)
    threshold_config_version: str = Field(alias="thresholdConfigVersion", min_length=1)
    baseline_checksum: str = Field(alias="baselineChecksum", pattern=r"^sha256:[0-9a-f]{64}$")
    feature_schema_version: int = Field(alias="featureSchemaVersion", ge=1)
    workspace_version: str = Field(alias="workspaceVersion", min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")
    metrics: MetricReportV1

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("evaluation_run", value)
        return value


class DetectionEvaluateRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: int | None = Field(default=None, alias="fromSequence", ge=0)
    to_sequence: int | None = Field(default=None, alias="toSequence", ge=0)
    dry_run: bool = Field(default=False, alias="dryRun")


class DetectionEvaluateResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    candidates_emitted: int = Field(alias="candidatesEmitted", ge=0)
    alerts_persisted: int = Field(alias="alertsPersisted", ge=0)
    alerts_suppressed: int = Field(alias="alertsSuppressed", ge=0)
    evaluations: list[RuleEvaluationV1]
    deterministic_checksum: str = Field(alias="deterministicChecksum", min_length=1)
