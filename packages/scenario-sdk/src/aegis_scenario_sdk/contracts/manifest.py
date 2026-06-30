"""Scenario manifest contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import AssetType, NodeStatus, RelationshipType
from aegis_contracts.primitives import AssetId, ClusterId, EdgeId, ScenarioId, SimTimestamp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_scenario_sdk.primitives import ScenarioLocalId
from aegis_scenario_sdk.version import SCENARIO_MANIFEST_SCHEMA_VERSION


class ScenarioMetadataV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    scenario_id: ScenarioId = Field(alias="scenarioId")
    name: str = Field(min_length=1)
    description: str = ""
    version: str = Field(min_length=1)
    required_platform_version: str = Field(alias="requiredPlatformVersion", min_length=1)


class ZoneDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ClusterId
    label: str = Field(min_length=1)
    security_level: str = Field(default="standard", alias="securityLevel")


class AssetTemplateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: AssetId
    asset_type: AssetType = Field(alias="assetType")
    label: str = Field(min_length=1)
    zone_id: ClusterId = Field(alias="zoneId")
    criticality: float = Field(ge=0.0, le=1.0)
    initial_risk_score: float = Field(alias="initialRiskScore", ge=0.0, le=1.0)
    initial_status: NodeStatus = Field(default=NodeStatus.NORMAL, alias="initialStatus")
    tags: list[str] = Field(default_factory=list)


class RelationshipTemplateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: EdgeId
    source: AssetId
    target: AssetId
    relationship_type: RelationshipType = Field(alias="relationshipType")
    directed: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    risk_contribution: float = Field(alias="riskContribution", ge=0.0, le=1.0)


class BehaviorPluginConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    plugin_id: str = Field(alias="pluginId", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class GeneratorScheduleV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    interval_sim_seconds: float = Field(alias="intervalSimSeconds", gt=0.0)
    jitter_sim_seconds: float = Field(default=0.0, alias="jitterSimSeconds", ge=0.0)


class GeneratorDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    target_asset_id: AssetId = Field(alias="targetAssetId")
    plugin: BehaviorPluginConfigV1
    schedule: GeneratorScheduleV1 | None = None


class HiddenConditionVisibilityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: str = Field(default="hidden_until_triggered")
    reveal_after_sim_seconds: float | None = Field(
        default=None, alias="revealAfterSimSeconds", ge=0.0
    )


class HiddenConditionDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    cause_label: str = Field(alias="causeLabel", min_length=1)
    trigger_refs: list[ScenarioLocalId] = Field(alias="triggerRefs")
    effect_refs: list[ScenarioLocalId] = Field(alias="effectRefs")
    visibility: HiddenConditionVisibilityV1


class ScheduledEventDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    sim_time: SimTimestamp = Field(alias="simTime")
    priority: int = Field(ge=0)
    tie_breaker: int = Field(alias="tieBreaker", ge=0)
    action: BehaviorPluginConfigV1


class BranchOutcomeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target_ref: ScenarioLocalId = Field(alias="targetRef")
    description: str = ""


class OutcomeBranchDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    label: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)
    trigger_condition: str = Field(alias="triggerCondition", min_length=1)
    outcomes: list[BranchOutcomeV1] = Field(min_length=1)


class ObjectiveDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    label: str = Field(min_length=1)
    success_criteria: str = Field(alias="successCriteria", min_length=1)
    failure_criteria: str = Field(default="", alias="failureCriteria")


class ScoringCriterionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    label: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)
    description: str = ""


class ScoringDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    max_score: float = Field(alias="maxScore", gt=0.0)
    criteria: list[ScoringCriterionV1] = Field(min_length=1)
    rubric: str = ""


class MediaReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    path: str = Field(min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)
    description: str = ""


class ScenarioManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    metadata: ScenarioMetadataV1
    zones: list[ZoneDefinitionV1] = Field(default_factory=list)
    assets: list[AssetTemplateV1] = Field(min_length=1)
    relationships: list[RelationshipTemplateV1] = Field(default_factory=list)
    generators: list[GeneratorDefinitionV1] = Field(default_factory=list)
    hidden_conditions: list[HiddenConditionDefinitionV1] = Field(
        default_factory=list, alias="hiddenConditions"
    )
    scheduled_events: list[ScheduledEventDefinitionV1] = Field(
        default_factory=list, alias="scheduledEvents"
    )
    objectives: list[ObjectiveDefinitionV1] = Field(default_factory=list)
    branches: list[OutcomeBranchDefinitionV1] = Field(default_factory=list)
    scoring: ScoringDefinitionV1
    media: list[MediaReferenceV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScenarioManifestV1:
        if self.schema_version != SCENARIO_MANIFEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported scenario manifest schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self

    def sim_time_values(self) -> list[datetime]:
        return [event.sim_time for event in self.scheduled_events]
