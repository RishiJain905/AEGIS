"""Simulation runtime contracts owned by Phase 09."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.events import ActorRef
from aegis_contracts.primitives import (
    AssetId,
    AuthoredId,
    Revision,
    RunId,
    Sequence,
    SimTimestamp,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    NORMALIZED_EVENT_HASH_SCHEMA_VERSION,
    RUN_CONFIGURATION_SCHEMA_VERSION,
    SCHEDULED_EVENT_SCHEMA_VERSION,
    SIMULATION_CHECKPOINT_SCHEMA_VERSION,
    SIMULATION_COMMAND_SCHEMA_VERSION,
    WORLD_STATE_SNAPSHOT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class SimulationRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class SimulationCommandType(StrEnum):
    START = "start"
    STEP = "step"
    ADVANCE = "advance"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    EXECUTE = "execute"


class ScheduledEventSourceType(StrEnum):
    SCHEDULED = "scheduled"
    GENERATOR = "generator"


class RunConfigurationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scenario_version_id: AuthoredId = Field(alias="scenarioVersionId")
    seed: int
    engine_version: str = Field(alias="engineVersion", min_length=1)
    initial_sim_time: SimTimestamp = Field(alias="initialSimTime")
    recorded_at_epoch: SimTimestamp = Field(alias="recordedAtEpoch")
    max_steps: int | None = Field(default=None, alias="maxSteps", ge=1)

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunConfigurationV1:
        assert_supported_schema_version("run_configuration", self.schema_version)
        if self.schema_version != RUN_CONFIGURATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run configuration schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScheduledEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    event_id: str = Field(alias="eventId", min_length=1)
    sim_time: SimTimestamp = Field(alias="simTime")
    priority: int = Field(ge=0)
    tie_breaker: int = Field(alias="tieBreaker", ge=0)
    source_type: ScheduledEventSourceType = Field(alias="sourceType")
    plugin_id: str = Field(alias="pluginId", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    target_asset_id: AssetId | None = Field(default=None, alias="targetAssetId")
    branch_gate_group: str | None = Field(default=None, alias="branchGateGroup")
    branch_gate_branch_id: str | None = Field(default=None, alias="branchGateBranchId")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScheduledEventV1:
        assert_supported_schema_version("scheduled_event", self.schema_version)
        if self.schema_version != SCHEDULED_EVENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported scheduled event schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class SimulationCommandV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    command_id: str = Field(alias="commandId", min_length=1)
    command_type: SimulationCommandType = Field(alias="commandType")
    run_id: RunId = Field(alias="runId")
    actor: ActorRef
    authorization_token: str | None = Field(default=None, alias="authorizationToken")
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> SimulationCommandV1:
        assert_supported_schema_version("simulation_command", self.schema_version)
        if self.schema_version != SIMULATION_COMMAND_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported simulation command schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AssetInstanceSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: AssetId
    asset_type: str = Field(alias="assetType", min_length=1)
    #: Security posture — what the attacker did to this asset.
    status: str = Field(min_length=1)
    #: Defensive controls the response toolkit has applied, in application order. Additive
    #: with a default, so checkpoints written before posture and controls were separated
    #: still restore at the same schema version (their collapsed ``status`` is split back
    #: out on restore).
    applied_controls: list[str] = Field(default_factory=list, alias="appliedControls")
    risk_score: float = Field(alias="riskScore", ge=0.0, le=1.0)
    criticality: float = Field(ge=0.0, le=1.0)
    zone_id: str = Field(alias="zoneId", min_length=1)
    revision: Revision


class RelationshipInstanceSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: AuthoredId
    source_id: AssetId = Field(alias="sourceId")
    target_id: AssetId = Field(alias="targetId")
    relationship_type: str = Field(alias="relationshipType", min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_contribution: float = Field(alias="riskContribution", ge=0.0, le=1.0)
    revision: Revision


class GeneratorStateSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    generator_id: str = Field(alias="generatorId", min_length=1)
    target_asset_id: AssetId = Field(alias="targetAssetId")
    plugin_id: str = Field(alias="pluginId", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    next_sim_time: SimTimestamp = Field(alias="nextSimTime")
    interval_sim_seconds: int = Field(alias="intervalSimSeconds", ge=1)
    jitter_sim_seconds: int = Field(alias="jitterSimSeconds", ge=0)


class HiddenConditionStateSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    condition_id: str = Field(alias="conditionId", min_length=1)
    revealed: bool
    triggered: bool
    trigger_count: int = Field(default=0, alias="triggerCount", ge=0)


class CampaignRuntimeStateSnapshotV1(BaseModel):
    """Serialized progression of one attacker kill-chain campaign.

    Everything the engine needs to resume a campaign mid-flight: where the attacker is
    standing, what it has established, which scripted reactions have already fired, and
    the scheduling bookkeeping that keeps exactly one advance in the event queue. Sets are
    serialized as sorted lists so the checkpoint checksum is stable.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    campaign_id: str = Field(alias="campaignId", min_length=1)
    status: str = Field(min_length=1)
    active: bool
    current_foothold_id: AssetId | None = Field(default=None, alias="currentFootholdId")
    established_footholds: list[AssetId] = Field(
        default_factory=list, alias="establishedFootholds"
    )
    #: capability id -> the asset whose compromise granted it (revoking that asset kills it).
    established_capabilities: dict[str, str] = Field(
        default_factory=dict, alias="establishedCapabilities"
    )
    revoked_capabilities: list[str] = Field(default_factory=list, alias="revokedCapabilities")
    completed_technique_ids: list[str] = Field(
        default_factory=list, alias="completedTechniqueIds"
    )
    next_technique_index: int = Field(default=0, alias="nextTechniqueIndex", ge=0)
    pending_anchor_id: AssetId | None = Field(default=None, alias="pendingAnchorId")
    fired_reaction_ids: list[str] = Field(default_factory=list, alias="firedReactionIds")
    schedule_seq: int = Field(default=0, alias="scheduleSeq", ge=0)
    advance_pending: bool = Field(default=False, alias="advancePending")
    dwell_multiplier: float = Field(default=1.0, alias="dwellMultiplier", gt=0.0)
    signals_suppressed: bool = Field(default=False, alias="signalsSuppressed")
    #: asset id -> the execution-halting status already accounted for on it.
    halted_assets: dict[str, str] = Field(default_factory=dict, alias="haltedAssets")


class RunOutcomeSnapshotV1(BaseModel):
    """The resolved win/lose verdict for a run, once (and only once) it resolves."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    outcome: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    resolved_sim_time: SimTimestamp = Field(alias="resolvedSimTime")
    resolved_sequence: Sequence = Field(alias="resolvedSequence", ge=1)
    #: Fraction of the org (criticality-weighted) currently out of service by defender action.
    disruption_cost: float = Field(alias="disruptionCost", ge=0.0, le=1.0)
    peak_disruption_cost: float = Field(alias="peakDisruptionCost", ge=0.0, le=1.0)
    #: Critical assets the attacker never held that the defender took fully out of service.
    needless_critical_outages: list[AssetId] = Field(
        default_factory=list, alias="needlessCriticalOutages"
    )
    neutralized_campaign_ids: list[str] = Field(
        default_factory=list, alias="neutralizedCampaignIds"
    )
    succeeded_campaign_ids: list[str] = Field(
        default_factory=list, alias="succeededCampaignIds"
    )


class WorldStateSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    status: SimulationRunStatus
    sim_time: SimTimestamp = Field(alias="simTime")
    next_sequence: Sequence = Field(alias="nextSequence", ge=1)
    assets: list[AssetInstanceSnapshotV1]
    relationships: list[RelationshipInstanceSnapshotV1]
    generators: list[GeneratorStateSnapshotV1]
    hidden_conditions: list[HiddenConditionStateSnapshotV1] = Field(
        default_factory=list,
        alias="hiddenConditions",
    )
    selected_branches: dict[str, str] = Field(default_factory=dict, alias="selectedBranches")
    pending_events: list[ScheduledEventV1] = Field(default_factory=list, alias="pendingEvents")
    rng_state: dict[str, list[int]] = Field(default_factory=dict, alias="rngState")
    # Phase 2 game loop. Additive with defaults, so checkpoints written before Phase 2
    # still restore (as a campaign-free, unresolved world) at the same schema version.
    campaigns: list[CampaignRuntimeStateSnapshotV1] = Field(default_factory=list)
    peak_disruption_cost: float = Field(
        default=0.0, alias="peakDisruptionCost", ge=0.0, le=1.0
    )
    outcome: RunOutcomeSnapshotV1 | None = None

    @model_validator(mode="after")
    def validate_schema_version(self) -> WorldStateSnapshotV1:
        assert_supported_schema_version("world_state_snapshot", self.schema_version)
        if self.schema_version != WORLD_STATE_SNAPSHOT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported world state snapshot schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class SimulationCheckpointV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: str = Field(min_length=1)
    run_id: RunId = Field(alias="runId")
    sequence_at_checkpoint: Sequence = Field(alias="sequenceAtCheckpoint", ge=0)
    engine_version: str = Field(alias="engineVersion", min_length=1)
    checksum: str = Field(min_length=1)
    world_state: WorldStateSnapshotV1 = Field(alias="worldState")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> SimulationCheckpointV1:
        assert_supported_schema_version("simulation_checkpoint", self.schema_version)
        if self.schema_version != SIMULATION_CHECKPOINT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported simulation checkpoint schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class NormalizedEventHashV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scenario_version_id: AuthoredId = Field(alias="scenarioVersionId")
    seed: int
    engine_version: str = Field(alias="engineVersion", min_length=1)
    hash_value: str = Field(alias="hash", min_length=1)
    event_count: int = Field(alias="eventCount", ge=0)

    @model_validator(mode="after")
    def validate_schema_version(self) -> NormalizedEventHashV1:
        assert_supported_schema_version("normalized_event_hash", self.schema_version)
        if self.schema_version != NORMALIZED_EVENT_HASH_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported normalized event hash schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
