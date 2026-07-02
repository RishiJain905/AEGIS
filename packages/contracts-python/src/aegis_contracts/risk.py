"""Phase 17 graph risk propagation contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import RelationshipType
from aegis_contracts.primitives import AssetId, EdgeId, RunId, Sequence, SimTimestamp
from aegis_contracts.versioning import (
    ASSET_RISK_SCORE_SCHEMA_VERSION,
    RISK_COMPUTE_REQUEST_SCHEMA_VERSION,
    RISK_COMPUTE_RESPONSE_SCHEMA_VERSION,
    RISK_CONTRIBUTION_SCHEMA_VERSION,
    RISK_ENGINE_CONFIG_SCHEMA_VERSION,
    RISK_EXPLANATION_PATH_SCHEMA_VERSION,
    RISK_INPUT_SCHEMA_VERSION,
    RISK_PROJECTION_DELTA_SCHEMA_VERSION,
    RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION,
    assert_supported_schema_version,
)

GRAPH_RISK_ALGORITHM_VERSION: str = "graph-risk-v1"


class RiskSignalSourceType(StrEnum):
    RULE = "rule"
    MODEL = "model"


class RiskSignalStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class RiskInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    signal_id: str = Field(alias="signalId", min_length=1)
    run_id: RunId = Field(alias="runId")
    source_type: RiskSignalSourceType = Field(alias="sourceType")
    asset_id: AssetId = Field(alias="assetId")
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    sim_time: SimTimestamp = Field(alias="simTime")
    deduplication_key: str = Field(alias="deduplicationKey", min_length=1)
    status: RiskSignalStatus = RiskSignalStatus.ACTIVE
    provenance_ref: str = Field(alias="provenanceRef", min_length=1)
    detector_id: str | None = Field(default=None, alias="detectorId")
    rule_id: str | None = Field(default=None, alias="ruleId")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_input", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskInputV1:
        if self.schema_version != RISK_INPUT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk input schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskEngineConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1)
    global_cap: float = Field(alias="globalCap", ge=0.0, le=1.0, default=1.0)
    max_hops: int = Field(alias="maxHops", ge=1, le=16, default=4)
    distance_decay_factor: float = Field(alias="distanceDecayFactor", ge=0.0, le=1.0, default=0.65)
    temporal_decay_factor: float = Field(
        alias="temporalDecayFactor", ge=0.0, le=1.0, default=0.5
    )
    temporal_half_life_seconds: float = Field(
        alias="temporalHalfLifeSeconds", gt=0.0, default=3600.0
    )
    criticality_amplifier: float = Field(alias="criticalityAmplifier", ge=0.0, le=1.0, default=0.25)
    min_explanation_contribution: float = Field(
        alias="minExplanationContribution", ge=0.0, le=1.0, default=0.01
    )
    relationship_type_weights: dict[str, float] = Field(
        alias="relationshipTypeWeights",
        default_factory=lambda: {item.value: 1.0 for item in RelationshipType},
    )
    eligible_relationship_types: list[RelationshipType] = Field(
        alias="eligibleRelationshipTypes",
        default_factory=lambda: list(RelationshipType),
    )
    top_explanation_paths: int = Field(alias="topExplanationPaths", ge=1, le=20, default=5)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_engine_config", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskEngineConfigV1:
        if self.schema_version != RISK_ENGINE_CONFIG_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk engine config schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.algorithm_version != GRAPH_RISK_ALGORITHM_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=f"Unsupported algorithm version: {self.algorithm_version}",
                details={"algorithmVersion": self.algorithm_version},
            )
        for weight in self.relationship_type_weights.values():
            if weight < 0.0 or weight > 1.0:
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message="Relationship type weights must be within [0, 1]",
                    details={"weight": weight},
                )
        return self


class RiskPathHopV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    edge_id: EdgeId = Field(alias="edgeId")
    source_id: AssetId = Field(alias="sourceId")
    target_id: AssetId = Field(alias="targetId")
    relationship_type: RelationshipType = Field(alias="relationshipType")
    edge_weight: float = Field(alias="edgeWeight", ge=0.0, le=1.0)
    hop_index: int = Field(alias="hopIndex", ge=1)


class RiskExplanationPathV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    signal_id: str = Field(alias="signalId", min_length=1)
    origin_asset_id: AssetId = Field(alias="originAssetId")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    node_ids: list[AssetId] = Field(alias="nodeIds", min_length=1)
    hops: list[RiskPathHopV1] = Field(min_length=0)
    hop_count: int = Field(alias="hopCount", ge=0)
    distance_decay: float = Field(alias="distanceDecay", ge=0.0, le=1.0)
    temporal_decay: float = Field(alias="temporalDecay", ge=0.0, le=1.0)
    criticality_factor: float = Field(alias="criticalityFactor", ge=1.0)
    contribution: float = Field(ge=0.0, le=1.0)
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_explanation_path", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskExplanationPathV1:
        if self.schema_version != RISK_EXPLANATION_PATH_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk explanation path schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskContributionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    signal_id: str = Field(alias="signalId", min_length=1)
    origin_asset_id: AssetId = Field(alias="originAssetId")
    target_asset_id: AssetId = Field(alias="targetAssetId")
    amount: float = Field(ge=0.0, le=1.0)
    hop_count: int = Field(alias="hopCount", ge=0)
    distance_decay: float = Field(alias="distanceDecay", ge=0.0, le=1.0)
    temporal_decay: float = Field(alias="temporalDecay", ge=0.0, le=1.0)
    criticality_factor: float = Field(alias="criticalityFactor", ge=1.0)
    explanation_path: RiskExplanationPathV1 = Field(alias="explanationPath")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_contribution", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskContributionV1:
        if self.schema_version != RISK_CONTRIBUTION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk contribution schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AssetRiskScoreV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    asset_id: AssetId = Field(alias="assetId")
    total: float = Field(ge=0.0, le=1.0)
    direct: float = Field(ge=0.0, le=1.0)
    propagated: float = Field(ge=0.0, le=1.0)
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1)
    computed_at_sequence: Sequence = Field(alias="computedAtSequence", ge=0)
    sim_time: SimTimestamp = Field(alias="simTime")
    top_contributions: list[RiskContributionV1] = Field(
        alias="topContributions",
        default_factory=list,
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("asset_risk_score", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> AssetRiskScoreV1:
        if self.schema_version != ASSET_RISK_SCORE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported asset risk score schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.total > self.direct + self.propagated + 1e-9:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="Total risk cannot exceed direct + propagated decomposition",
                details={
                    "total": self.total,
                    "direct": self.direct,
                    "propagated": self.propagated,
                },
            )
        return self


class RiskProjectionNodeUpdateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: AssetId = Field(alias="assetId")
    risk_score: float = Field(alias="riskScore", ge=0.0, le=1.0)
    direct: float = Field(ge=0.0, le=1.0)
    propagated: float = Field(ge=0.0, le=1.0)
    revision: int = Field(ge=0)


class RiskProjectionDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence = Field(ge=0)
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1)
    node_updates: list[RiskProjectionNodeUpdateV1] = Field(alias="nodeUpdates", min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_projection_delta", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskProjectionDeltaV1:
        if self.schema_version != RISK_PROJECTION_DELTA_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk projection delta schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskComputeRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    from_sequence: Sequence | None = Field(default=None, alias="fromSequence")
    to_sequence: Sequence | None = Field(default=None, alias="toSequence")
    dry_run: bool = Field(default=False, alias="dryRun")
    incident_seed_asset_ids: list[AssetId] | None = Field(
        default=None, alias="incidentSeedAssetIds"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_compute_request", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskComputeRequestV1:
        if self.schema_version != RISK_COMPUTE_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk compute request schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskComputeResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1)
    scores_computed: int = Field(alias="scoresComputed", ge=0)
    nodes_updated: int = Field(alias="nodesUpdated", ge=0)
    events_persisted: int = Field(alias="eventsPersisted", ge=0)
    checksum: str = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_compute_response", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskComputeResponseV1:
        if self.schema_version != RISK_COMPUTE_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported risk compute response schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RiskScoresListResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    scores: list[AssetRiskScoreV1]

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        assert_supported_schema_version("risk_scores_list_response", value)
        return value

    @model_validator(mode="after")
    def validate_version(self) -> RiskScoresListResponseV1:
        if self.schema_version != RISK_SCORES_LIST_RESPONSE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    f"Unsupported risk scores list response schema version: {self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self
