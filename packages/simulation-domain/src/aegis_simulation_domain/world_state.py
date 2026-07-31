"""World state materialization and mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aegis_contracts.killchain import (
    is_control_status,
    project_effective_status,
    project_node_status,
)
from aegis_contracts.simulation import (
    AssetInstanceSnapshotV1,
    CampaignRuntimeStateSnapshotV1,
    GeneratorStateSnapshotV1,
    HiddenConditionStateSnapshotV1,
    RelationshipInstanceSnapshotV1,
    RunOutcomeSnapshotV1,
    ScheduledEventSourceType,
    ScheduledEventV1,
    SimulationRunStatus,
    WorldStateSnapshotV1,
)
from aegis_contracts.versioning import (
    SCHEDULED_EVENT_SCHEMA_VERSION,
    WORLD_STATE_SNAPSHOT_SCHEMA_VERSION,
)
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1

from aegis_simulation_domain.clock import VirtualClock
from aegis_simulation_domain.event_queue import DeterministicEventQueue
from aegis_simulation_domain.random_streams import SeededRandomStreams


@dataclass
class AssetState:
    """One asset's world state: what the attacker did to it, and what we did about it.

    These are two independent facts and the world has to hold both. ``status`` is the
    asset's *security posture* — the attacker-driven, manifest-baselined value from the
    ``NodeStatus`` vocabulary (``normal``/``suspicious``/``under_investigation``/
    ``contained``/``compromised``). ``applied_controls`` is the set of *defensive controls*
    the response toolkit has put on it, in the richer ``ContainmentStatus`` vocabulary
    (``observed``, ``isolated``, ``credentials_revoked``, ...).

    Collapsing the two into one field is what made "Observe" destructive: the operator
    watched a compromised host and the world forgot it was compromised, because the
    control overwrote the posture. Keeping them apart means a control can never erase an
    intrusion, and the after-action can still say what was compromised and when.

    Controls accumulate in application order and are deduplicated, so the tuple doubles as
    the deterministic record of which controls are live on the asset right now.
    """

    id: str
    asset_type: str
    status: str
    risk_score: float
    criticality: float
    zone_id: str
    revision: int = 0
    applied_controls: tuple[str, ...] = ()

    def apply_status(self, status: str) -> None:
        """Apply one status value from either vocabulary without erasing the other.

        The single entry point for ``effect.set_asset_status`` on every path that mutates
        an asset — the live plugin handler, the cold rebuild that re-applies persisted
        effect events, and the ghost-branch counterfactual engine — so all three compose
        the world identically and a rebuilt runtime matches a live one exactly.

        Control values land in :attr:`applied_controls`; anything else (a posture value,
        or an unrecognized authored status) sets the posture. ``revision`` always advances:
        something was applied to this asset, and consumers diff on revision.
        """
        if is_control_status(status):
            if status not in self.applied_controls:
                self.applied_controls = (*self.applied_controls, status)
        else:
            self.status = status
        self.revision += 1

    def lift_controls(self) -> None:
        """Take every defensive control back off the asset, leaving its posture intact.

        Lifting is already part of the model the proportionality scoring assumes —
        containment that has since been lifted stops counting against the defender — even
        though no allowlisted command produces it yet. Keeping it here means the posture
        underneath survives the lift, which is the whole point of the split: an asset that
        is un-isolated goes back to being visibly compromised, not visibly fine.
        """
        if self.applied_controls:
            self.applied_controls = ()
            self.revision += 1

    @property
    def effective_status(self) -> str:
        """The single operator-facing status this asset projects to. See
        :func:`aegis_contracts.killchain.project_effective_status`."""
        return project_effective_status(self.status, self.applied_controls).value


@dataclass
class RelationshipState:
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    risk_contribution: float
    revision: int = 0


@dataclass
class GeneratorState:
    generator_id: str
    target_asset_id: str
    plugin_id: str
    config: dict[str, object]
    next_sim_time: datetime
    interval_sim_seconds: int
    jitter_sim_seconds: int


@dataclass
class HiddenConditionState:
    condition_id: str
    revealed: bool = False
    triggered: bool = False
    trigger_count: int = 0


@dataclass
class CampaignRuntimeState:
    """In-world progression of an active attacker kill-chain campaign.

    Held on ``WorldState`` and mutated deterministically by the runtime as techniques
    advance on the sim clock. Progression is a pure function of (seed, world state,
    action sequence), so a fresh run at the same seed reproduces it exactly and
    ``deepcopy`` (ghost/counterfactual clones) carries it faithfully.

    As of Phase 2 this round-trips through ``WorldStateSnapshotV1``, so checkpoint
    save/restore and replay reconstruct a mid-flight campaign exactly — including which
    reactions have already fired and where the next advance is scheduled.
    """

    campaign_id: str
    status: str  # aegis_contracts.CampaignStatus value
    active: bool = True
    current_foothold_id: str | None = None
    established_footholds: set[str] = field(default_factory=set)
    # capability id -> the asset whose compromise granted it. Containing that asset
    # (isolate / revoke credentials) kills the capability, which is how credential
    # revocation cuts credential-dependent techniques.
    established_capabilities: dict[str, str] = field(default_factory=dict)
    # Monotonic: once a capability is cut it stays cut, even if the asset is restored.
    revoked_capabilities: set[str] = field(default_factory=set)
    completed_technique_ids: list[str] = field(default_factory=list)
    # Index of the technique currently scheduled to execute next.
    next_technique_index: int = 0
    # Anchor asset resolved for the currently scheduled advance (resolved at schedule time).
    pending_anchor_id: str | None = None
    fired_reaction_ids: set[str] = field(default_factory=set)
    # Monotonic counter making each scheduled advance's event id unique + deterministic.
    # It doubles as a staleness token: a queued advance whose ``scheduleSeq`` no longer
    # matches has been superseded by a reschedule and is skipped.
    schedule_seq: int = 0
    # Whether exactly one advance is already queued (keeps re-anchoring reactions from
    # enqueuing duplicate advances).
    advance_pending: bool = False
    # Scripted stealth adaptation: every remaining dwell is scaled by this, and suppressed
    # signals stop the campaign emitting the telemetry detection feeds on.
    dwell_multiplier: float = 1.0
    signals_suppressed: bool = False
    # asset id -> the execution-halting status already accounted for, so a service that
    # stays "restarting" resets the attacker's dwell once per interruption, not per step.
    halted_assets: dict[str, str] = field(default_factory=dict)

    def to_snapshot(self) -> CampaignRuntimeStateSnapshotV1:
        return CampaignRuntimeStateSnapshotV1(
            campaign_id=self.campaign_id,
            status=self.status,
            active=self.active,
            current_foothold_id=self.current_foothold_id,
            established_footholds=sorted(self.established_footholds),
            established_capabilities=dict(sorted(self.established_capabilities.items())),
            revoked_capabilities=sorted(self.revoked_capabilities),
            completed_technique_ids=list(self.completed_technique_ids),
            next_technique_index=self.next_technique_index,
            pending_anchor_id=self.pending_anchor_id,
            fired_reaction_ids=sorted(self.fired_reaction_ids),
            schedule_seq=self.schedule_seq,
            advance_pending=self.advance_pending,
            dwell_multiplier=self.dwell_multiplier,
            signals_suppressed=self.signals_suppressed,
            halted_assets=dict(sorted(self.halted_assets.items())),
        )

    @classmethod
    def from_snapshot(cls, snapshot: CampaignRuntimeStateSnapshotV1) -> CampaignRuntimeState:
        return cls(
            campaign_id=snapshot.campaign_id,
            status=snapshot.status,
            active=snapshot.active,
            current_foothold_id=snapshot.current_foothold_id,
            established_footholds=set(snapshot.established_footholds),
            established_capabilities=dict(snapshot.established_capabilities),
            revoked_capabilities=set(snapshot.revoked_capabilities),
            completed_technique_ids=list(snapshot.completed_technique_ids),
            next_technique_index=snapshot.next_technique_index,
            pending_anchor_id=snapshot.pending_anchor_id,
            fired_reaction_ids=set(snapshot.fired_reaction_ids),
            schedule_seq=snapshot.schedule_seq,
            advance_pending=snapshot.advance_pending,
            dwell_multiplier=snapshot.dwell_multiplier,
            signals_suppressed=snapshot.signals_suppressed,
            halted_assets=dict(snapshot.halted_assets),
        )


@dataclass
class WorldState:
    status: SimulationRunStatus = SimulationRunStatus.CREATED
    assets: dict[str, AssetState] = field(default_factory=dict)
    relationships: dict[str, RelationshipState] = field(default_factory=dict)
    generators: dict[str, GeneratorState] = field(default_factory=dict)
    hidden_conditions: dict[str, HiddenConditionState] = field(default_factory=dict)
    selected_branches: dict[str, str] = field(default_factory=dict)
    campaigns: dict[str, CampaignRuntimeState] = field(default_factory=dict)
    # High-water mark of the defender's collateral cost; a briefly-catastrophic
    # over-containment still counts against proportionality after it is lifted.
    peak_disruption_cost: float = 0.0
    # The run's win/lose verdict, set exactly once when the race resolves.
    outcome: RunOutcomeSnapshotV1 | None = None
    next_sequence: int = 1

    @classmethod
    def from_manifest(cls, manifest: ScenarioManifestV1, clock: VirtualClock) -> WorldState:
        world = cls(status=SimulationRunStatus.CREATED)
        for asset in manifest.assets:
            world.assets[asset.id] = AssetState(
                id=asset.id,
                asset_type=asset.asset_type,
                status=asset.initial_status,
                risk_score=asset.initial_risk_score,
                criticality=asset.criticality,
                zone_id=asset.zone_id,
            )
        for relationship in manifest.relationships:
            world.relationships[relationship.id] = RelationshipState(
                id=relationship.id,
                source_id=relationship.source,
                target_id=relationship.target,
                relationship_type=relationship.relationship_type,
                confidence=relationship.confidence,
                risk_contribution=relationship.risk_contribution,
            )
        for generator in manifest.generators:
            if generator.schedule is None:
                continue
            schedule = generator.schedule
            world.generators[generator.id] = GeneratorState(
                generator_id=generator.id,
                target_asset_id=generator.target_asset_id,
                plugin_id=generator.plugin.plugin_id,
                config=dict(generator.plugin.config),
                next_sim_time=clock.sim_time
                + timedelta(seconds=schedule.interval_sim_seconds),
                interval_sim_seconds=int(schedule.interval_sim_seconds),
                jitter_sim_seconds=int(schedule.jitter_sim_seconds),
            )
        for condition in manifest.hidden_conditions:
            world.hidden_conditions[condition.id] = HiddenConditionState(condition_id=condition.id)
        return world

    def seed_queue(self, manifest: ScenarioManifestV1, queue: DeterministicEventQueue) -> None:
        scheduled: list[ScheduledEventV1] = []
        for event in manifest.scheduled_events:
            config = dict(event.action.config)
            target_asset_id = event.target_asset_id
            if target_asset_id is None and event.action.plugin_id == "effect.set_asset_status":
                if "assetId" in config:
                    target_asset_id = str(config["assetId"])
                else:
                    for condition in manifest.hidden_conditions:
                        if event.id in condition.effect_refs:
                            for trigger_ref in condition.trigger_refs:
                                for gen in manifest.generators:
                                    if gen.id == trigger_ref:
                                        target_asset_id = gen.target_asset_id
                                        config["assetId"] = target_asset_id
            scheduled.append(
                ScheduledEventV1(
                    schema_version=SCHEDULED_EVENT_SCHEMA_VERSION,
                    event_id=event.id,
                    sim_time=event.sim_time,
                    priority=event.priority,
                    tie_breaker=event.tie_breaker,
                    source_type=ScheduledEventSourceType.SCHEDULED,
                    plugin_id=event.action.plugin_id,
                    config=config,
                    target_asset_id=target_asset_id,
                    branch_gate_group=(
                        event.branch_gate.branch_group if event.branch_gate is not None else None
                    ),
                    branch_gate_branch_id=(
                        event.branch_gate.branch_id if event.branch_gate is not None else None
                    ),
                )
            )
        for generator in self.generators.values():
            scheduled.append(
                ScheduledEventV1(
                    schema_version=SCHEDULED_EVENT_SCHEMA_VERSION,
                    event_id=generator.generator_id,
                    sim_time=generator.next_sim_time,
                    priority=10,
                    tie_breaker=0,
                    source_type=ScheduledEventSourceType.GENERATOR,
                    plugin_id=generator.plugin_id,
                    config=dict(generator.config),
                    target_asset_id=generator.target_asset_id,
                )
            )
        queue.enqueue_many(scheduled)

    def to_snapshot(
        self,
        *,
        clock: VirtualClock,
        queue: DeterministicEventQueue,
        rng: SeededRandomStreams,
    ) -> WorldStateSnapshotV1:
        return WorldStateSnapshotV1(
            schema_version=WORLD_STATE_SNAPSHOT_SCHEMA_VERSION,
            status=self.status,
            sim_time=clock.sim_time,
            next_sequence=self.next_sequence,
            assets=[
                AssetInstanceSnapshotV1(
                    id=asset.id,
                    asset_type=asset.asset_type,
                    status=asset.status,
                    applied_controls=list(asset.applied_controls),
                    risk_score=asset.risk_score,
                    criticality=asset.criticality,
                    zone_id=asset.zone_id,
                    revision=asset.revision,
                )
                for asset in sorted(self.assets.values(), key=lambda item: item.id)
            ],
            relationships=[
                RelationshipInstanceSnapshotV1(
                    id=relationship.id,
                    source_id=relationship.source_id,
                    target_id=relationship.target_id,
                    relationship_type=relationship.relationship_type,
                    confidence=relationship.confidence,
                    risk_contribution=relationship.risk_contribution,
                    revision=relationship.revision,
                )
                for relationship in sorted(self.relationships.values(), key=lambda item: item.id)
            ],
            generators=[
                GeneratorStateSnapshotV1(
                    generator_id=generator.generator_id,
                    target_asset_id=generator.target_asset_id,
                    plugin_id=generator.plugin_id,
                    config=dict(generator.config),
                    next_sim_time=generator.next_sim_time,
                    interval_sim_seconds=generator.interval_sim_seconds,
                    jitter_sim_seconds=generator.jitter_sim_seconds,
                )
                for generator in sorted(
                    self.generators.values(), key=lambda item: item.generator_id
                )
            ],
            hidden_conditions=[
                HiddenConditionStateSnapshotV1(
                    condition_id=condition.condition_id,
                    revealed=condition.revealed,
                    triggered=condition.triggered,
                    trigger_count=condition.trigger_count,
                )
                for condition in sorted(
                    self.hidden_conditions.values(),
                    key=lambda item: item.condition_id,
                )
            ],
            selected_branches=dict(sorted(self.selected_branches.items())),
            pending_events=queue.to_list(),
            rng_state=rng.to_snapshot(),
            campaigns=[
                state.to_snapshot()
                for _, state in sorted(self.campaigns.items(), key=lambda item: item[0])
            ],
            peak_disruption_cost=self.peak_disruption_cost,
            outcome=self.outcome,
        )

    def restore_from_snapshot(self, snapshot: WorldStateSnapshotV1) -> None:
        self.status = snapshot.status
        self.next_sequence = snapshot.next_sequence
        self.assets = {asset.id: _restore_asset(asset) for asset in snapshot.assets}
        self.relationships = {
            relationship.id: RelationshipState(
                id=relationship.id,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                relationship_type=relationship.relationship_type,
                confidence=relationship.confidence,
                risk_contribution=relationship.risk_contribution,
                revision=relationship.revision,
            )
            for relationship in snapshot.relationships
        }
        self.generators = {
            generator.generator_id: GeneratorState(
                generator_id=generator.generator_id,
                target_asset_id=generator.target_asset_id,
                plugin_id=generator.plugin_id,
                config=dict(generator.config),
                next_sim_time=generator.next_sim_time,
                interval_sim_seconds=generator.interval_sim_seconds,
                jitter_sim_seconds=generator.jitter_sim_seconds,
            )
            for generator in snapshot.generators
        }
        self.hidden_conditions = {
            condition.condition_id: HiddenConditionState(
                condition_id=condition.condition_id,
                revealed=condition.revealed,
                triggered=condition.triggered,
                trigger_count=condition.trigger_count,
            )
            for condition in snapshot.hidden_conditions
        }
        self.selected_branches = dict(snapshot.selected_branches)
        self.campaigns = {
            campaign.campaign_id: CampaignRuntimeState.from_snapshot(campaign)
            for campaign in snapshot.campaigns
        }
        self.peak_disruption_cost = snapshot.peak_disruption_cost
        self.outcome = snapshot.outcome


def _restore_asset(asset: AssetInstanceSnapshotV1) -> AssetState:
    """Rebuild one asset from a checkpoint, upgrading pre-split checkpoints in place.

    Checkpoints written before posture and controls were separated stored one collapsed
    ``status``, which for a contained asset holds a control value. Restoring that straight
    into ``status`` would leave a posture the graph vocabulary does not accept and a set of
    controls the disruption model cannot see, so a resumed run would forget every
    containment the operator had applied. Splitting it back out is lossy in one direction
    only — the posture underneath a legacy containment was already overwritten and is
    unrecoverable — so we project the control to the posture it implies, which is what the
    old world would have shown anyway.
    """
    status = asset.status
    controls = tuple(asset.applied_controls)
    if not controls and is_control_status(status):
        controls = (status,)
        status = project_node_status(status).value
    return AssetState(
        id=asset.id,
        asset_type=asset.asset_type,
        status=status,
        risk_score=asset.risk_score,
        criticality=asset.criticality,
        zone_id=asset.zone_id,
        revision=asset.revision,
        applied_controls=controls,
    )
