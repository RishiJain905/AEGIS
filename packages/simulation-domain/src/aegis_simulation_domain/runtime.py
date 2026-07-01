"""Deterministic simulation runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.simulation import (
    RunConfigurationV1,
    ScheduledEventSourceType,
    ScheduledEventV1,
    SimulationCheckpointV1,
    SimulationCommandType,
    SimulationCommandV1,
    SimulationRunStatus,
)
from aegis_contracts.versioning import (
    DOMAIN_EVENT_SCHEMA_VERSION,
    SCHEDULED_EVENT_SCHEMA_VERSION,
    SIMULATION_CHECKPOINT_SCHEMA_VERSION,
)
from aegis_scenario_sdk.compatibility import is_platform_version_compatible
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1

from aegis_simulation_domain.clock import VirtualClock
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode
from aegis_simulation_domain.event_queue import DeterministicEventQueue
from aegis_simulation_domain.handlers import execute_plugin
from aegis_simulation_domain.ids import derive_checkpoint_id, derive_event_id, derive_trace_id
from aegis_simulation_domain.normalized_hash import checkpoint_checksum
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.world_state import WorldState

SIMULATION_ENGINE_VERSION = "0.0.0-phase10"


@dataclass
class SimulationRuntime:
    run_id: str
    configuration: RunConfigurationV1
    manifest: ScenarioManifestV1
    clock: VirtualClock = field(init=False)
    queue: DeterministicEventQueue = field(init=False)
    rng: SeededRandomStreams = field(init=False)
    world: WorldState = field(init=False)
    events: list[DomainEventEnvelopeV1] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.clock = VirtualClock(self.configuration.initial_sim_time)
        self.queue = DeterministicEventQueue()
        self.rng = SeededRandomStreams(self.configuration.seed)
        self.world = WorldState.from_manifest(self.manifest, self.clock)

    def start(self) -> list[DomainEventEnvelopeV1]:
        if self.world.status not in {SimulationRunStatus.CREATED, SimulationRunStatus.STOPPED}:
            raise SimulationError(
                code=SimulationErrorCode.INVALID_STATE,
                message=f"Cannot start run in status {self.world.status}",
            )
        if not is_platform_version_compatible(self.manifest.metadata.required_platform_version):
            raise SimulationError(
                code=SimulationErrorCode.PLATFORM_INCOMPATIBLE,
                message=(
                    "Scenario requires platform version "
                    f"{self.manifest.metadata.required_platform_version}"
                ),
                details={
                    "requiredPlatformVersion": self.manifest.metadata.required_platform_version,
                },
            )
        self.world.status = SimulationRunStatus.RUNNING
        self.world.seed_queue(self.manifest, self.queue)
        return [self._lifecycle_event("sim.run.started")]

    def step(self) -> list[DomainEventEnvelopeV1]:
        if self.world.status != SimulationRunStatus.RUNNING:
            raise SimulationError(
                code=SimulationErrorCode.INVALID_STATE,
                message=f"Cannot step run in status {self.world.status}",
            )
        scheduled = self.queue.pop()
        if scheduled is None:
            return []
        return self._process_scheduled_event(scheduled)

    def advance(self, until: datetime) -> list[DomainEventEnvelopeV1]:
        emitted: list[DomainEventEnvelopeV1] = []
        while self.world.status == SimulationRunStatus.RUNNING:
            peek = self.queue.peek()
            if peek is None or peek.sim_time > until:
                break
            emitted.extend(self.step())
        return emitted

    def pause(self) -> list[DomainEventEnvelopeV1]:
        if self.world.status != SimulationRunStatus.RUNNING:
            raise SimulationError(
                code=SimulationErrorCode.INVALID_STATE,
                message="Can only pause a running simulation",
            )
        self.world.status = SimulationRunStatus.PAUSED
        return [self._lifecycle_event("sim.run.paused")]

    def resume(self) -> list[DomainEventEnvelopeV1]:
        if self.world.status != SimulationRunStatus.PAUSED:
            raise SimulationError(
                code=SimulationErrorCode.INVALID_STATE,
                message="Can only resume a paused simulation",
            )
        self.world.status = SimulationRunStatus.RUNNING
        return [self._lifecycle_event("sim.run.resumed")]

    def stop(self) -> list[DomainEventEnvelopeV1]:
        if self.world.status == SimulationRunStatus.STOPPED:
            raise SimulationError(
                code=SimulationErrorCode.INVALID_STATE,
                message="Simulation is already stopped",
            )
        self.world.status = SimulationRunStatus.STOPPED
        return [self._lifecycle_event("sim.run.stopped")]

    def checkpoint(self, *, created_at: datetime | None = None) -> SimulationCheckpointV1:
        checkpoint_id = derive_checkpoint_id(
            run_seed=self.configuration.seed,
            sequence=self.world.next_sequence,
        )
        checkpoint_event = self._lifecycle_event(
            "sim.checkpoint.created",
            payload={
                "checkpointId": checkpoint_id,
                "sequenceAtCheckpoint": self.world.next_sequence,
            },
        )
        snapshot = self.world.to_snapshot(clock=self.clock, queue=self.queue, rng=self.rng)
        payload = snapshot.model_dump(mode="json", by_alias=True)
        checksum = checkpoint_checksum(payload)
        checkpoint = SimulationCheckpointV1(
            schema_version=SIMULATION_CHECKPOINT_SCHEMA_VERSION,
            id=checkpoint_id,
            run_id=self.run_id,
            sequence_at_checkpoint=checkpoint_event.sequence,
            engine_version=SIMULATION_ENGINE_VERSION,
            checksum=checksum,
            world_state=snapshot,
            created_at=(created_at or self.configuration.recorded_at_epoch).astimezone(UTC),
        )
        return checkpoint

    def restore(self, checkpoint: SimulationCheckpointV1) -> None:
        if checkpoint.engine_version != SIMULATION_ENGINE_VERSION:
            raise SimulationError(
                code=SimulationErrorCode.CHECKPOINT_INCOMPATIBLE,
                message="Checkpoint engine version is incompatible",
                details={
                    "expected": SIMULATION_ENGINE_VERSION,
                    "actual": checkpoint.engine_version,
                },
            )
        payload = checkpoint.world_state.model_dump(mode="json", by_alias=True)
        expected = checkpoint_checksum(payload)
        if expected != checkpoint.checksum:
            raise SimulationError(
                code=SimulationErrorCode.CHECKPOINT_CHECKSUM_INVALID,
                message="Checkpoint checksum mismatch",
                details={"expected": expected, "actual": checkpoint.checksum},
            )
        self.world.restore_from_snapshot(checkpoint.world_state)
        self.clock = VirtualClock.from_snapshot(checkpoint.world_state.sim_time)
        self.queue = DeterministicEventQueue.from_list(checkpoint.world_state.pending_events)
        self.rng.restore_from_snapshot(checkpoint.world_state.rng_state)

    def execute_command(self, command: SimulationCommandV1) -> list[DomainEventEnvelopeV1]:
        self._validate_authorization(command)
        if command.command_type == SimulationCommandType.START:
            return self.start()
        if command.command_type == SimulationCommandType.STEP:
            return self.step()
        if command.command_type == SimulationCommandType.ADVANCE:
            until_raw = command.payload.get("until")
            if until_raw is None:
                raise SimulationError(
                    code=SimulationErrorCode.VALIDATION_FAILED,
                    message="advance command requires until in payload",
                )
            until = datetime.fromisoformat(str(until_raw).replace("Z", "+00:00")).astimezone(UTC)
            return self.advance(until)
        if command.command_type == SimulationCommandType.PAUSE:
            return self.pause()
        if command.command_type == SimulationCommandType.RESUME:
            return self.resume()
        if command.command_type == SimulationCommandType.STOP:
            return self.stop()
        if command.command_type == SimulationCommandType.CHECKPOINT:
            self.checkpoint()
            return list(self.events[-1:])
        if command.command_type == SimulationCommandType.RESTORE:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message="Use SimulationEngine.restore_checkpoint for restore commands",
            )
        if command.command_type == SimulationCommandType.EXECUTE:
            plugin_id = str(command.payload.get("pluginId", ""))
            config = dict(command.payload.get("config", {}))
            target_asset_id = command.payload.get("targetAssetId")
            result = execute_plugin(
                plugin_id=plugin_id,
                config=config,
                target_asset_id=str(target_asset_id) if target_asset_id else None,
                world=self.world,
                run_id=self.run_id,
                run_seed=self.configuration.seed,
                sequence=self.world.next_sequence,
                sim_time=self.clock.sim_time,
                recorded_at_epoch=self.configuration.recorded_at_epoch,
                rng=self.rng,
                manifest=self.manifest,
            )
            for event in result.events:
                self._record_event(event)
            command_event = self._lifecycle_event(
                "sim.command.executed",
                payload={
                    "commandId": command.command_id,
                    "commandType": command.command_type.value,
                },
            )
            self._record_event(command_event)
            return [*result.events, command_event]
        msg = f"Unsupported command type: {command.command_type}"
        raise SimulationError(code=SimulationErrorCode.VALIDATION_FAILED, message=msg)

    def run_steps(self, count: int) -> list[DomainEventEnvelopeV1]:
        emitted: list[DomainEventEnvelopeV1] = []
        for _ in range(count):
            if self.world.status != SimulationRunStatus.RUNNING:
                break
            batch = self.step()
            if not batch:
                break
            emitted.extend(batch)
        return emitted

    def _process_scheduled_event(self, scheduled: ScheduledEventV1) -> list[DomainEventEnvelopeV1]:
        if scheduled.branch_gate_group is not None and scheduled.branch_gate_branch_id is not None:
            selected = self.world.selected_branches.get(scheduled.branch_gate_group)
            if selected != scheduled.branch_gate_branch_id:
                return []
        self.clock.advance_to(scheduled.sim_time)
        generator = None
        if scheduled.source_type == ScheduledEventSourceType.GENERATOR:
            generator = self.world.generators.get(scheduled.event_id)
        target_asset_id = scheduled.target_asset_id
        if target_asset_id is None and scheduled.plugin_id == "effect.set_asset_status":
            target_asset_id = self._resolve_status_effect_target(scheduled.event_id)
            scheduled = scheduled.model_copy(update={"target_asset_id": target_asset_id})
            if target_asset_id and "assetId" not in scheduled.config:
                scheduled = scheduled.model_copy(
                    update={"config": {**scheduled.config, "assetId": target_asset_id}}
                )
        result = execute_plugin(
            plugin_id=scheduled.plugin_id,
            config=scheduled.config,
            target_asset_id=target_asset_id,
            world=self.world,
            run_id=self.run_id,
            run_seed=self.configuration.seed,
            sequence=self.world.next_sequence,
            sim_time=self.clock.sim_time,
            recorded_at_epoch=self.configuration.recorded_at_epoch,
            rng=self.rng,
            generator=generator,
            manifest=self.manifest,
        )
        emitted: list[DomainEventEnvelopeV1] = []
        trigger_source_id = (
            generator.generator_id if generator is not None else scheduled.event_id
        )
        for event in result.events:
            self._record_event(event)
            emitted.append(event)
            trigger_events = self._process_hidden_condition_triggers(
                event,
                trigger_source_id,
            )
            emitted.extend(trigger_events)
        emitted.extend(self._process_hidden_condition_reveals())
        if result.reschedule is not None and generator is not None:
            self.queue.enqueue(
                ScheduledEventV1(
                    schema_version=SCHEDULED_EVENT_SCHEMA_VERSION,
                    event_id=generator.generator_id,
                    sim_time=result.reschedule,
                    priority=10,
                    tie_breaker=0,
                    source_type=ScheduledEventSourceType.GENERATOR,
                    plugin_id=generator.plugin_id,
                    config=dict(generator.config),
                    target_asset_id=generator.target_asset_id,
                )
            )
        return emitted

    def _process_hidden_condition_triggers(
        self,
        event: DomainEventEnvelopeV1,
        trigger_source_id: str,
    ) -> list[DomainEventEnvelopeV1]:
        if not event.type.startswith("telemetry."):
            return []
        emitted: list[DomainEventEnvelopeV1] = []
        for definition in self.manifest.hidden_conditions:
            if trigger_source_id not in definition.trigger_refs:
                continue
            state = self.world.hidden_conditions.get(definition.id)
            if state is None or state.triggered:
                continue
            state.trigger_count += 1
            if state.trigger_count < definition.trigger_threshold:
                continue
            state.triggered = True
            emitted.append(
                self._lifecycle_event(
                    "sim.hidden_condition.triggered",
                    payload={"conditionId": definition.id},
                )
            )
        return emitted

    def _process_hidden_condition_reveals(self) -> list[DomainEventEnvelopeV1]:
        elapsed_seconds = (
            self.clock.sim_time - self.configuration.initial_sim_time
        ).total_seconds()
        emitted: list[DomainEventEnvelopeV1] = []
        for definition in self.manifest.hidden_conditions:
            state = self.world.hidden_conditions.get(definition.id)
            if state is None or state.revealed:
                continue
            timed_reveal = definition.visibility.reveal_after_sim_seconds
            should_reveal = state.triggered or (
                timed_reveal is not None and elapsed_seconds >= timed_reveal
            )
            if not should_reveal:
                continue
            state.revealed = True
            emitted.append(
                self._lifecycle_event(
                    "sim.hidden_condition.revealed",
                    payload={"conditionId": definition.id},
                )
            )
        return emitted

    def _resolve_status_effect_target(self, scheduled_event_id: str) -> str | None:
        for condition in self.manifest.hidden_conditions:
            if scheduled_event_id in condition.effect_refs:
                for trigger_ref in condition.trigger_refs:
                    generator = self.world.generators.get(trigger_ref)
                    if generator is not None:
                        return generator.target_asset_id
        for generator in self.world.generators.values():
            return generator.target_asset_id
        return None

    def _record_event(self, event: DomainEventEnvelopeV1) -> None:
        self.events.append(event)
        self.world.next_sequence = max(self.world.next_sequence, event.sequence + 1)

    def _lifecycle_event(
        self, event_type: str, payload: dict[str, object] | None = None
    ) -> DomainEventEnvelopeV1:
        sequence = self.world.next_sequence
        event = DomainEventEnvelopeV1(
            event_id=derive_event_id(
                run_seed=self.configuration.seed,
                sequence=sequence,
                event_type=event_type,
            ),
            run_id=self.run_id,
            sequence=sequence,
            type=event_type,
            schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
            sim_time=self.clock.sim_time,
            recorded_at=self.configuration.recorded_at_epoch + timedelta(milliseconds=sequence),
            actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
            subject=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
            payload={"schemaVersion": 1, **(payload or {})},
            trace_id=derive_trace_id(run_seed=self.configuration.seed, sequence=sequence),
        )
        self._record_event(event)
        return event

    def _validate_authorization(self, command: SimulationCommandV1) -> None:
        if command.actor.type == ActorType.AGENT:
            raise SimulationError(
                code=SimulationErrorCode.UNAUTHORIZED,
                message="Agents cannot directly mutate simulation state",
                details={"actorType": command.actor.type.value},
            )
        if (
            command.command_type
            in {
                SimulationCommandType.EXECUTE,
                SimulationCommandType.START,
                SimulationCommandType.STOP,
                SimulationCommandType.CHECKPOINT,
                SimulationCommandType.RESTORE,
            }
            and not command.authorization_token
        ):
            raise SimulationError(
                code=SimulationErrorCode.UNAUTHORIZED,
                message="Authorization token required for state-changing commands",
            )
