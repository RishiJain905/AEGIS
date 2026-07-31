"""Scenario manifest contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import AssetType, NodeStatus, RelationshipType
from aegis_contracts.killchain import AttackTactic, is_control_status
from aegis_contracts.primitives import AssetId, ClusterId, EdgeId, ScenarioId, SimTimestamp
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    trigger_threshold: int = Field(default=1, alias="triggerThreshold", ge=1)


class BranchGateDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    branch_group: str = Field(alias="branchGroup", min_length=1)
    branch_id: ScenarioLocalId = Field(alias="branchId")


class ScheduledEventDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    sim_time: SimTimestamp = Field(alias="simTime")
    priority: int = Field(ge=0)
    tie_breaker: int = Field(alias="tieBreaker", ge=0)
    action: BehaviorPluginConfigV1
    branch_gate: BranchGateDefinitionV1 | None = Field(default=None, alias="branchGate")
    target_asset_id: AssetId | None = Field(default=None, alias="targetAssetId")


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
    branch_group: str | None = Field(default=None, alias="branchGroup")


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


class AnchorSelectorMode(StrEnum):
    """How a kill-chain technique chooses the asset it targets (its *anchor*)."""

    BY_ID = "by_id"
    BY_ASSET_TYPE = "by_asset_type"
    ALONG_EDGE = "along_edge"


class EdgeDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class AnchorSelectorV1(BaseModel):
    """Declarative rule selecting a technique's anchor asset.

    ``by_id`` names an asset outright (entry, crown-jewel, egress). ``along_edge``
    traverses a real relationship edge of ``relationship_type`` from the campaign's
    current foothold (or ``from_asset_id`` when set) — the deterministic backbone of
    lateral movement / privilege escalation over the org's true topology.
    ``by_asset_type`` picks the lowest-id asset of a type (crown-jewel fallback).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: AnchorSelectorMode
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    asset_type: AssetType | None = Field(default=None, alias="assetType")
    relationship_type: RelationshipType | None = Field(
        default=None, alias="relationshipType"
    )
    direction: EdgeDirection = EdgeDirection.OUTBOUND
    from_asset_id: AssetId | None = Field(default=None, alias="fromAssetId")


class TechniqueSignalTarget(StrEnum):
    ANCHOR = "anchor"
    FOOTHOLD = "foothold"


class TechniqueSignalV1(BaseModel):
    """A telemetry beat the technique emits so detection/investigation can catch it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    plugin: BehaviorPluginConfigV1
    target: TechniqueSignalTarget = TechniqueSignalTarget.ANCHOR


class KillChainTechniqueV1(BaseModel):
    """One ATT&CK technique (a tactic realized by a specific technique id)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    tactic: AttackTactic
    attack_technique_id: str = Field(alias="attackTechniqueId", min_length=1)
    name: str = Field(min_length=1)
    anchor: AnchorSelectorV1
    dwell_sim_seconds: float = Field(alias="dwellSimSeconds", gt=0.0)
    #: The *posture* this technique drives its anchor into. Restricted to the attacker's
    #: half of the vocabulary: ``contained`` is the one value the posture and defensive
    #: control vocabularies share, and it is classified as a control (ADR 0036), so an
    #: authored ``contained`` would be written as a posture by the live engine and as a
    #: control by the cold rebuild — the two would disagree about the same event stream.
    #: It is also meaningless as an attacker outcome, so rejecting it at authoring time
    #: costs nothing and keeps the two paths provably identical.
    compromise_status: NodeStatus = Field(
        default=NodeStatus.COMPROMISED, alias="compromiseStatus"
    )
    moves_foothold: bool = Field(default=True, alias="movesFoothold")
    signals: list[TechniqueSignalV1] = Field(default_factory=list)
    establishes: list[str] = Field(default_factory=list)
    #: Capabilities this technique consumes. Revoking the credential/identity that granted
    #: one (containing its establishing asset) blocks the technique outright — the
    #: "cut credential-based stages" lever from the response toolkit.
    requires_capabilities: list[str] = Field(
        default_factory=list, alias="requiresCapabilities"
    )

    @field_validator("compromise_status")
    @classmethod
    def _reject_control_compromise_status(cls, value: NodeStatus) -> NodeStatus:
        if is_control_status(value.value):
            raise ValueError(
                "compromiseStatus must be an attacker posture, not the defensive "
                f"control '{value.value}'"
            )
        return value


class ReactionPreconditionType(StrEnum):
    FOOTHOLD_ISOLATED = "foothold_isolated"
    ASSET_STATUS_IS = "asset_status_is"
    CAPABILITY_REVOKED = "capability_revoked"
    #: The asset the in-flight technique is reaching for has been contained.
    PENDING_ANCHOR_DISRUPTED = "pending_anchor_disrupted"
    #: Every asset the attacker holds has been contained — its last-ditch trigger.
    ALL_FOOTHOLDS_DISRUPTED = "all_footholds_disrupted"


_DEFAULT_DISRUPTED_STATUSES = ("contained", "isolated", "quarantined")


class ReactionPreconditionV1(BaseModel):
    """A declarative predicate over world state that arms a scripted counter-move."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: ReactionPreconditionType
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    statuses: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_DISRUPTED_STATUSES)
    )
    capability: str | None = None


class ReactionCounterMoveType(StrEnum):
    PIVOT_TO_ASSET = "pivot_to_asset"
    ACTIVATE_TECHNIQUE = "activate_technique"
    GO_QUIET = "go_quiet"
    STALL = "stall"


class ReactionCounterMoveV1(BaseModel):
    """The scripted move an attacker makes when a precondition fires.

    A counter may only use capability the attacker has already established in-world:
    ``pivot_to_asset`` requires an already-compromised foothold; ``activate_technique``
    a pre-declared persistence/backup technique (optionally gated on ``requires_capability``)
    — which is also how a campaign *escalates*, by jumping straight to a later, louder
    technique. ``go_quiet`` trades speed for stealth: it rescales every remaining dwell by
    ``dwell_multiplier`` and can drop the technique's telemetry beats entirely, so the
    attacker becomes slower but far harder to detect. ``stall`` models running out of
    options — a defensive win.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: ReactionCounterMoveType
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    technique_id: ScenarioLocalId | None = Field(default=None, alias="techniqueId")
    requires_capability: str | None = Field(default=None, alias="requiresCapability")
    dwell_multiplier: float = Field(default=1.0, alias="dwellMultiplier", gt=0.0)
    suppress_signals: bool = Field(default=False, alias="suppressSignals")


class ReactionRuleV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    precondition: ReactionPreconditionV1
    counter_move: ReactionCounterMoveV1 = Field(alias="counterMove")


class KillChainCampaignV1(BaseModel):
    """An ordered ATT&CK technique graph bound to a seed-selected root-cause branch."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ScenarioLocalId
    name: str = Field(min_length=1)
    bound_branch_group: str = Field(alias="boundBranchGroup", min_length=1)
    bound_branch_id: ScenarioLocalId = Field(alias="boundBranchId")
    entry_anchor: AnchorSelectorV1 = Field(alias="entryAnchor")
    techniques: list[KillChainTechniqueV1] = Field(min_length=1)
    reactions: list[ReactionRuleV1] = Field(default_factory=list)


class ProportionalityPolicyV1(BaseModel):
    """Thresholds that decide when containment stopped being proportionate.

    ``disruption_cost`` is the criticality-weighted fraction of the org the defender has
    currently taken out of service (see
    :mod:`aegis_simulation_domain.disruption`). Crossing ``warn_threshold`` turns a clean
    win into a *costly* win; crossing ``fail_threshold`` — or needlessly crippling
    ``needless_critical_outage_limit`` critical services the attacker never held — loses
    the run outright even if the attacker was stopped.

    Defaults are deliberately generous enough that a focused response (isolating the
    handful of assets actually on the attacker's path) never trips them.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    warn_threshold: float = Field(default=0.15, alias="warnThreshold", ge=0.0, le=1.0)
    fail_threshold: float = Field(default=0.35, alias="failThreshold", ge=0.0, le=1.0)
    needless_critical_outage_limit: int = Field(
        default=2, alias="needlessCriticalOutageLimit", ge=1
    )
    critical_asset_threshold: float = Field(
        default=0.9, alias="criticalAssetThreshold", ge=0.0, le=1.0
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> ProportionalityPolicyV1:
        if self.fail_threshold < self.warn_threshold:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="proportionality.failThreshold must be >= warnThreshold",
                details={
                    "warnThreshold": self.warn_threshold,
                    "failThreshold": self.fail_threshold,
                },
            )
        return self


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
    campaigns: list[KillChainCampaignV1] = Field(default_factory=list)
    proportionality: ProportionalityPolicyV1 = Field(default_factory=ProportionalityPolicyV1)
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
