"""World state materialization and mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aegis_contracts.simulation import (
    AssetInstanceSnapshotV1,
    GeneratorStateSnapshotV1,
    HiddenConditionStateSnapshotV1,
    RelationshipInstanceSnapshotV1,
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
    id: str
    asset_type: str
    status: str
    risk_score: float
    criticality: float
    zone_id: str
    revision: int = 0


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
class WorldState:
    status: SimulationRunStatus = SimulationRunStatus.CREATED
    assets: dict[str, AssetState] = field(default_factory=dict)
    relationships: dict[str, RelationshipState] = field(default_factory=dict)
    generators: dict[str, GeneratorState] = field(default_factory=dict)
    hidden_conditions: dict[str, HiddenConditionState] = field(default_factory=dict)
    selected_branches: dict[str, str] = field(default_factory=dict)
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
        )

    def restore_from_snapshot(self, snapshot: WorldStateSnapshotV1) -> None:
        self.status = snapshot.status
        self.next_sequence = snapshot.next_sequence
        self.assets = {
            asset.id: AssetState(
                id=asset.id,
                asset_type=asset.asset_type,
                status=asset.status,
                risk_score=asset.risk_score,
                criticality=asset.criticality,
                zone_id=asset.zone_id,
                revision=asset.revision,
            )
            for asset in snapshot.assets
        }
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
