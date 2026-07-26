"""Deterministic simulation runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.killchain import (
    KILLCHAIN_CAMPAIGN_ACTIVATED,
    KILLCHAIN_CAMPAIGN_CONTAINED,
    KILLCHAIN_CAMPAIGN_STALLED,
    KILLCHAIN_EXFILTRATION_COMPLETED,
    KILLCHAIN_REACTION_FIRED,
    KILLCHAIN_TECHNIQUE_DISRUPTED,
    KILLCHAIN_TECHNIQUE_EXECUTED,
    RUN_OUTCOME_RESOLVED,
    AttackTactic,
    CampaignStatus,
    DisruptionEffect,
)
from aegis_contracts.simulation import (
    RunConfigurationV1,
    RunOutcomeSnapshotV1,
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
from aegis_scenario_sdk.contracts.manifest import (
    KillChainCampaignV1,
    ReactionCounterMoveType,
    ReactionRuleV1,
    ScenarioManifestV1,
    TechniqueSignalTarget,
)

from aegis_simulation_domain.clock import VirtualClock
from aegis_simulation_domain.disruption import (
    DisruptionAssessment,
    assess_disruption,
    attacker_held_asset_ids,
    compute_business_disruption,
)
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode
from aegis_simulation_domain.event_queue import DeterministicEventQueue
from aegis_simulation_domain.handlers import execute_plugin
from aegis_simulation_domain.ids import derive_checkpoint_id, derive_event_id, derive_trace_id
from aegis_simulation_domain.killchain import (
    counter_move_available,
    find_campaign,
    precondition_met,
    resolve_anchor,
    technique_index,
)
from aegis_simulation_domain.normalized_hash import checkpoint_checksum
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.resolution import RunResolution, evaluate_run_outcome
from aegis_simulation_domain.world_state import CampaignRuntimeState, WorldState

SIMULATION_ENGINE_VERSION = "0.0.0-phase10"

# Internal, engine-only scheduled-event plugin id: the attacker campaign enqueues these to
# advance a technique on the sim clock. It is never authored in a manifest (so the plugin
# registry / scenario validation never see it) — the runtime intercepts it before the
# allowlisted-plugin dispatch. Priority sits between authored effects (<=4) and telemetry
# generators (10) so an advance resolves deterministically against same-time telemetry.
_KILLCHAIN_ADVANCE_PLUGIN = "killchain.advance"
_KILLCHAIN_ADVANCE_PRIORITY = 5


@dataclass(frozen=True)
class _DisruptionPass:
    """Events emitted by the disruption pass plus the reading each campaign was given."""

    events: list[DomainEventEnvelopeV1]
    by_campaign: dict[str, DisruptionAssessment]


def _primary_effect(assessment: DisruptionAssessment) -> DisruptionEffect:
    """The single most decisive thing the defender took away, for event reporting.

    Ordered by how final it is: egress being cut ends the run whatever else is true, a
    revoked credential cannot be worked around, a severed foothold might still have a
    fallback, and a severed anchor is the mildest — the attacker can re-aim.
    """
    if assessment.egress_blocked:
        return DisruptionEffect.EGRESS_BLOCKED
    if assessment.blocking_capabilities:
        return DisruptionEffect.CAPABILITY_REVOKED
    if assessment.foothold_severed:
        return DisruptionEffect.FOOTHOLD_SEVERED
    return DisruptionEffect.ANCHOR_SEVERED


def _pending_tactic(campaign: KillChainCampaignV1, state: CampaignRuntimeState) -> str | None:
    index = state.next_technique_index
    if 0 <= index < len(campaign.techniques):
        return campaign.techniques[index].tactic.value
    return None


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
        events = self._process_scheduled_event(scheduled)
        # Order is load-bearing and deterministic: read what the defender has severed,
        # give the campaign's authored counter-moves the first chance to answer it, then
        # fall back / contain whatever is still cut off, then see if the run is decided.
        assessments = self._process_killchain_disruption()
        events.extend(assessments.events)
        events.extend(self._process_killchain_reactions(assessments.by_campaign))
        events.extend(self._resolve_blocked_campaigns())
        events.extend(self._evaluate_run_outcome(horizon_reached=self.queue.peek() is None))
        try:
            from aegis_observability.instrumentation import record_simulation_events

            record_simulation_events(count=len(events), status="ok")
        except Exception:  # noqa: BLE001
            pass
        return events

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
        # Stopping is how a run reaches its horizon (the ticker stops a run once the
        # scenario's step budget is spent), so this is the last chance to put a verdict on
        # an engagement that neither side closed out.
        emitted = self._evaluate_run_outcome(horizon_reached=True)
        self.world.status = SimulationRunStatus.STOPPED
        emitted.append(self._lifecycle_event("sim.run.stopped"))
        return emitted

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

    def snapshot_checkpoint(
        self, *, created_at: datetime | None = None
    ) -> SimulationCheckpointV1:
        """Build a runtime checkpoint without emitting a ``sim.checkpoint.created`` event.

        Unlike :meth:`checkpoint`, this is a pure read of the current world/clock/queue/rng
        state and does not mutate the runtime or its event stream. It is used by restart
        recovery to persist a faithfully restorable snapshot (lifecycle status + RNG streams
        + clock + world) after each command without perturbing the authoritative,
        determinism-golden event sequence.
        """
        sequence = self.world.next_sequence
        snapshot = self.world.to_snapshot(clock=self.clock, queue=self.queue, rng=self.rng)
        payload = snapshot.model_dump(mode="json", by_alias=True)
        checksum = checkpoint_checksum(payload)
        created = created_at or (
            self.configuration.recorded_at_epoch + timedelta(milliseconds=sequence)
        )
        return SimulationCheckpointV1(
            schema_version=SIMULATION_CHECKPOINT_SCHEMA_VERSION,
            id=derive_checkpoint_id(run_seed=self.configuration.seed, sequence=sequence),
            run_id=self.run_id,
            sequence_at_checkpoint=sequence,
            engine_version=SIMULATION_ENGINE_VERSION,
            checksum=checksum,
            world_state=snapshot,
            created_at=created.astimezone(UTC),
        )

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
        if scheduled.plugin_id == _KILLCHAIN_ADVANCE_PLUGIN:
            advance_events = self._process_killchain_advance(scheduled)
            advance_events.extend(self._process_hidden_condition_reveals())
            advance_events.extend(self._maybe_activate_campaigns())
            return advance_events
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
        emitted.extend(self._maybe_activate_campaigns())
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

    # ------------------------------------------------------------------ #
    # Attacker kill-chain engine (Phase 1)                                #
    # ------------------------------------------------------------------ #

    def _maybe_activate_campaigns(self) -> list[DomainEventEnvelopeV1]:
        """Activate any campaign whose bound root-cause branch is now selected.

        Idempotent: each campaign activates at most once (on the first step after its
        branch is chosen). Campaign-free scenarios and unselected branches produce nothing,
        so behaviour is byte-identical for everything except the seed that selects the
        bound branch.
        """
        emitted: list[DomainEventEnvelopeV1] = []
        for campaign in self.manifest.campaigns:
            if campaign.id in self.world.campaigns:
                continue
            selected = self.world.selected_branches.get(campaign.bound_branch_group)
            if selected != campaign.bound_branch_id:
                continue
            entry = resolve_anchor(
                campaign.entry_anchor,
                world=self.world,
                foothold_id=None,
                rng=self.rng,
                stream_key=f"killchain.entry:{campaign.id}",
            )
            state = CampaignRuntimeState(
                campaign_id=campaign.id,
                status=CampaignStatus.ACTIVE.value,
                active=True,
                current_foothold_id=entry,
            )
            if entry is not None:
                state.established_footholds.add(entry)
            self.world.campaigns[campaign.id] = state
            emitted.append(
                self._killchain_event(
                    KILLCHAIN_CAMPAIGN_ACTIVATED,
                    entry,
                    {
                        "campaignId": campaign.id,
                        "campaignName": campaign.name,
                        "boundBranchId": campaign.bound_branch_id,
                        "entryAssetId": entry,
                    },
                )
            )
            self._schedule_advance(state, campaign, 0, self.clock.sim_time)
        return emitted

    def _schedule_advance(
        self,
        state: CampaignRuntimeState,
        campaign: KillChainCampaignV1,
        index: int,
        base_time: datetime,
        *,
        reschedule: bool = False,
    ) -> None:
        """Resolve technique ``index``'s anchor and queue its execution after its dwell.

        Keeps exactly one *live* advance per campaign. Without ``reschedule`` an already
        queued advance is only re-targeted (used by re-anchoring reactions). With it, the
        campaign's ``schedule_seq`` is bumped so the queued advance is recognised as stale
        when it pops and a fresh one is enqueued from ``base_time`` — that is how a
        disrupted technique loses its accrued dwell and has to start over. The queue has
        no removal, so staleness is tracked by token rather than by deleting entries.
        """
        state.next_technique_index = index
        technique = campaign.techniques[index]
        state.pending_anchor_id = resolve_anchor(
            technique.anchor,
            world=self.world,
            foothold_id=state.current_foothold_id,
            rng=self.rng,
            stream_key=f"killchain.anchor:{campaign.id}:{index}",
        )
        if state.advance_pending and not reschedule:
            return
        state.advance_pending = True
        state.schedule_seq += 1
        dwell = technique.dwell_sim_seconds * state.dwell_multiplier
        sim_time = base_time + timedelta(seconds=dwell)
        self.queue.enqueue(
            ScheduledEventV1(
                schema_version=SCHEDULED_EVENT_SCHEMA_VERSION,
                event_id=f"killchain:{campaign.id}:{state.schedule_seq}",
                sim_time=sim_time,
                priority=_KILLCHAIN_ADVANCE_PRIORITY,
                tie_breaker=0,
                source_type=ScheduledEventSourceType.SCHEDULED,
                plugin_id=_KILLCHAIN_ADVANCE_PLUGIN,
                config={
                    "campaignId": campaign.id,
                    "techniqueIndex": index,
                    "scheduleSeq": state.schedule_seq,
                },
            )
        )

    def _process_killchain_advance(
        self, scheduled: ScheduledEventV1
    ) -> list[DomainEventEnvelopeV1]:
        """Execute the campaign's current technique and schedule the next one.

        Emits the technique's attacker telemetry (so detection can catch it), a truth
        ``technique_executed`` marker, and a ``sim.asset.status_changed`` compromising the
        anchor; then walks the campaign forward — moving the foothold, banking established
        capabilities, and resolving the next anchor over real edges — or resolving to
        exfiltration success.
        """
        campaign_id = str(scheduled.config.get("campaignId", ""))
        state = self.world.campaigns.get(campaign_id)
        campaign = find_campaign(self.manifest.campaigns, campaign_id)
        if state is None or campaign is None:
            return []
        # A superseded advance (its technique was disrupted and rescheduled) still pops
        # off the queue. Drop it without clearing the flag — the replacement is live.
        schedule_seq = int(scheduled.config.get("scheduleSeq", state.schedule_seq))
        if schedule_seq != state.schedule_seq:
            return []
        state.advance_pending = False
        if not state.active:
            return []
        index = state.next_technique_index
        if index < 0 or index >= len(campaign.techniques):
            state.active = False
            return []
        technique = campaign.techniques[index]

        # The defender may have acted between the advance being queued and it coming due.
        # A technique whose foothold, target, egress or credential has been taken away
        # does not land: it is abandoned here and the disruption pass that runs later in
        # this same step decides whether the campaign falls back or is contained. A merely
        # interrupted technique (service restarting) keeps everything and simply starts
        # its dwell over.
        assessment = assess_disruption(campaign=campaign, state=state, world=self.world)
        if assessment.blocked:
            return []
        if assessment.halts_execution:
            self._schedule_advance(
                state, campaign, index, self.clock.sim_time, reschedule=True
            )
            return []

        anchor_id = state.pending_anchor_id
        emitted: list[DomainEventEnvelopeV1] = []

        # A campaign that has gone quiet stops emitting the telemetry detection feeds on;
        # from here the operator can only find it by investigating.
        signals = [] if state.signals_suppressed else technique.signals
        for signal in signals:
            target = (
                anchor_id
                if signal.target == TechniqueSignalTarget.ANCHOR
                else state.current_foothold_id
            )
            result = execute_plugin(
                plugin_id=signal.plugin.plugin_id,
                config=dict(signal.plugin.config),
                target_asset_id=target,
                world=self.world,
                run_id=self.run_id,
                run_seed=self.configuration.seed,
                sequence=self.world.next_sequence,
                sim_time=self.clock.sim_time,
                recorded_at_epoch=self.configuration.recorded_at_epoch,
                rng=self.rng,
                generator=None,
                manifest=self.manifest,
            )
            for event in result.events:
                self._record_event(event)
                emitted.append(event)

        emitted.append(
            self._killchain_event(
                KILLCHAIN_TECHNIQUE_EXECUTED,
                anchor_id,
                {
                    "campaignId": campaign_id,
                    "techniqueId": technique.id,
                    "tactic": technique.tactic.value,
                    "attackTechniqueId": technique.attack_technique_id,
                    "techniqueName": technique.name,
                    "anchorAssetId": anchor_id,
                    "status": technique.compromise_status.value,
                },
            )
        )

        if anchor_id is not None:
            asset = self.world.assets.get(anchor_id)
            if asset is not None:
                asset.status = technique.compromise_status.value
                asset.revision += 1
            emitted.append(
                self._killchain_event(
                    "sim.asset.status_changed",
                    anchor_id,
                    {"assetId": anchor_id, "status": technique.compromise_status.value},
                )
            )

        state.completed_technique_ids.append(technique.id)
        if anchor_id is not None:
            state.established_footholds.add(anchor_id)
        for capability in technique.establishes:
            # Anchor the capability to the asset that granted it, so containing that asset
            # later revokes it without the scenario having to author the linkage.
            state.established_capabilities[capability] = anchor_id or (
                state.current_foothold_id or ""
            )
        if technique.moves_foothold and anchor_id is not None:
            state.current_foothold_id = anchor_id

        if technique.tactic == AttackTactic.EXFILTRATION:
            state.active = False
            state.status = CampaignStatus.SUCCEEDED.value
            emitted.append(
                self._killchain_event(
                    KILLCHAIN_EXFILTRATION_COMPLETED,
                    anchor_id,
                    {
                        "campaignId": campaign_id,
                        "techniqueId": technique.id,
                        "anchorAssetId": anchor_id,
                    },
                )
            )
            return emitted

        next_index = index + 1
        if next_index < len(campaign.techniques):
            self._schedule_advance(state, campaign, next_index, self.clock.sim_time)
        else:
            state.active = False
        return emitted

    def _process_killchain_disruption(self) -> _DisruptionPass:
        """Read what defender containment has taken from each campaign, and apply it.

        Two effects land here directly because they are consequences, not choices: a
        capability whose granting asset has been contained is revoked for good, and a
        technique running on an asset the defender restarted or rolled back loses its
        accrued dwell and starts over. Everything else (fall back? go quiet? give up?) is
        left to the campaign's reaction rules and, failing those, to
        :meth:`_resolve_blocked_campaigns`.
        """
        events: list[DomainEventEnvelopeV1] = []
        by_campaign: dict[str, DisruptionAssessment] = {}
        for campaign_id in sorted(self.world.campaigns):
            state = self.world.campaigns[campaign_id]
            campaign = find_campaign(self.manifest.campaigns, campaign_id)
            if campaign is None or not state.active:
                continue
            assessment = assess_disruption(campaign=campaign, state=state, world=self.world)
            by_campaign[campaign_id] = assessment

            for capability in assessment.revoked_capabilities:
                if capability in state.revoked_capabilities:
                    continue
                state.revoked_capabilities.add(capability)
                events.append(
                    self._disruption_event(
                        campaign,
                        state,
                        effect=DisruptionEffect.CAPABILITY_REVOKED,
                        asset_id=state.established_capabilities.get(capability),
                        extra={"capability": capability},
                    )
                )

            halted_now = dict(assessment.halted_assets)
            for asset_id, status in sorted(halted_now.items()):
                if state.halted_assets.get(asset_id) == status:
                    continue
                state.halted_assets[asset_id] = status
                # The attacker loses its accrued dwell the moment the service goes down,
                # not when the advance was going to land.
                self._schedule_advance(
                    state,
                    campaign,
                    state.next_technique_index,
                    self.clock.sim_time,
                    reschedule=True,
                )
                events.append(
                    self._disruption_event(
                        campaign,
                        state,
                        effect=DisruptionEffect.DWELL_RESET,
                        asset_id=asset_id,
                        extra={"disruptedByStatus": status},
                    )
                )
            for asset_id in [a for a in state.halted_assets if a not in halted_now]:
                del state.halted_assets[asset_id]

        return _DisruptionPass(events=events, by_campaign=by_campaign)

    def _process_killchain_reactions(
        self, assessments: dict[str, DisruptionAssessment]
    ) -> list[DomainEventEnvelopeV1]:
        """Evaluate each active campaign's reaction rules against current world state.

        Deterministic and fire-once per rule. In an undisrupted run no precondition holds,
        so nothing fires and the event stream is exactly the base attacker plan; a
        defender action is what arms them.
        """
        emitted: list[DomainEventEnvelopeV1] = []
        for campaign_id in sorted(self.world.campaigns):
            state = self.world.campaigns[campaign_id]
            if not state.active:
                continue
            campaign = find_campaign(self.manifest.campaigns, campaign_id)
            if campaign is None:
                continue
            assessment = assessments.get(campaign_id)
            if assessment is None:
                assessment = assess_disruption(
                    campaign=campaign, state=state, world=self.world
                )
            for reaction in campaign.reactions:
                if reaction.id in state.fired_reaction_ids:
                    continue
                if not precondition_met(
                    reaction.precondition,
                    world=self.world,
                    state=state,
                    assessment=assessment,
                ):
                    continue
                state.fired_reaction_ids.add(reaction.id)
                emitted.extend(self._apply_counter_move(campaign, state, reaction))
        return emitted

    def _resolve_blocked_campaigns(self) -> list[DomainEventEnvelopeV1]:
        """Fall back, or admit defeat, for campaigns the defender has cut off.

        Re-assessed *after* reactions so an authored counter-move gets to answer the
        disruption first. What remains blocked adapts on its own, exactly as the design
        spec allows: re-establish from another asset the attacker already owns (never a
        new one — no teleporting), losing the accrued dwell in the process. With no
        usable foothold left, or with egress cut, or with a required credential revoked
        and no way around it, the campaign is contained and the defender has won the race.
        """
        emitted: list[DomainEventEnvelopeV1] = []
        for campaign_id in sorted(self.world.campaigns):
            state = self.world.campaigns[campaign_id]
            if not state.active:
                continue
            campaign = find_campaign(self.manifest.campaigns, campaign_id)
            if campaign is None:
                continue
            assessment = assess_disruption(campaign=campaign, state=state, world=self.world)
            if not assessment.blocked:
                continue

            effect = _primary_effect(assessment)
            emitted.append(
                self._disruption_event(
                    campaign,
                    state,
                    effect=effect,
                    asset_id=(
                        state.pending_anchor_id
                        if effect == DisruptionEffect.ANCHOR_SEVERED
                        else state.current_foothold_id
                    ),
                    extra={
                        "blockingCapabilities": list(assessment.blocking_capabilities),
                    },
                )
            )

            recoverable = assessment.foothold_severed and not (
                assessment.egress_blocked or assessment.blocking_capabilities
            )
            fallback = assessment.fallback_foothold_id if recoverable else None
            if fallback is not None:
                state.current_foothold_id = fallback
                self._schedule_advance(
                    state,
                    campaign,
                    state.next_technique_index,
                    self.clock.sim_time,
                    reschedule=True,
                )
                # The re-anchored technique may still point at a severed asset; if so the
                # next step's assessment contains the campaign rather than looping.
                continue

            state.active = False
            state.status = CampaignStatus.CONTAINED.value
            emitted.append(
                self._killchain_event(
                    KILLCHAIN_CAMPAIGN_CONTAINED,
                    state.current_foothold_id,
                    {
                        "campaignId": campaign.id,
                        "effect": effect.value,
                        "completedTechniqueIds": list(state.completed_technique_ids),
                        "reachedTactic": _pending_tactic(campaign, state),
                    },
                )
            )
        return emitted

    def _evaluate_run_outcome(self, *, horizon_reached: bool) -> list[DomainEventEnvelopeV1]:
        """Resolve the run's win/lose verdict, once.

        Only scenarios that author an attacker campaign have a race to resolve, so a
        campaign-free scenario never produces an outcome event and its event stream is
        untouched by this phase.
        """
        if not self.manifest.campaigns or self.world.outcome is not None:
            return []
        disruption = compute_business_disruption(
            world=self.world,
            attacker_held_asset_ids=attacker_held_asset_ids(self.world),
            policy=self.manifest.proportionality,
        )
        self.world.peak_disruption_cost = max(self.world.peak_disruption_cost, disruption.cost)
        resolution = evaluate_run_outcome(
            world=self.world,
            disruption=disruption,
            peak_disruption_cost=self.world.peak_disruption_cost,
            policy=self.manifest.proportionality,
            horizon_reached=horizon_reached,
        )
        if resolution is None:
            return []
        return [self._record_outcome(resolution)]

    def _record_outcome(self, resolution: RunResolution) -> DomainEventEnvelopeV1:
        outcome = RunOutcomeSnapshotV1(
            outcome=resolution.outcome.value,
            reason=resolution.reason.value,
            resolved_sim_time=self.clock.sim_time,
            resolved_sequence=self.world.next_sequence,
            disruption_cost=resolution.disruption_cost,
            peak_disruption_cost=resolution.peak_disruption_cost,
            needless_critical_outages=list(resolution.needless_critical_outages),
            neutralized_campaign_ids=list(resolution.neutralized_campaign_ids),
            succeeded_campaign_ids=list(resolution.succeeded_campaign_ids),
        )
        self.world.outcome = outcome
        return self._killchain_event(
            RUN_OUTCOME_RESOLVED,
            None,
            outcome.model_dump(mode="json", by_alias=True),
        )

    @property
    def run_outcome(self) -> RunOutcomeSnapshotV1 | None:
        """The run's resolved verdict, or ``None`` while the race is still on."""
        return self.world.outcome

    def _disruption_event(
        self,
        campaign: KillChainCampaignV1,
        state: CampaignRuntimeState,
        *,
        effect: DisruptionEffect,
        asset_id: str | None,
        extra: dict[str, object] | None = None,
    ) -> DomainEventEnvelopeV1:
        index = state.next_technique_index
        technique = (
            campaign.techniques[index] if 0 <= index < len(campaign.techniques) else None
        )
        payload: dict[str, object] = {
            "campaignId": campaign.id,
            "effect": effect.value,
            "assetId": asset_id,
            "techniqueId": technique.id if technique is not None else None,
            "attackTechniqueId": (
                technique.attack_technique_id if technique is not None else None
            ),
            "tactic": technique.tactic.value if technique is not None else None,
        }
        payload.update(extra or {})
        return self._killchain_event(KILLCHAIN_TECHNIQUE_DISRUPTED, asset_id, payload)

    def _apply_counter_move(
        self,
        campaign: KillChainCampaignV1,
        state: CampaignRuntimeState,
        reaction: ReactionRuleV1,
    ) -> list[DomainEventEnvelopeV1]:
        move = reaction.counter_move
        available = counter_move_available(
            move, campaign=campaign, state=state, world=self.world
        )
        emitted: list[DomainEventEnvelopeV1] = []
        outcome = "stalled"
        if not available or move.type == ReactionCounterMoveType.STALL:
            state.active = False
            state.status = CampaignStatus.STALLED.value
        elif move.type == ReactionCounterMoveType.PIVOT_TO_ASSET:
            state.current_foothold_id = str(move.asset_id)
            index = state.next_technique_index
            if 0 <= index < len(campaign.techniques):
                # Re-establishing from a different asset costs the attacker the dwell it
                # had accrued: it is starting the technique over from the new foothold.
                self._schedule_advance(
                    state, campaign, index, self.clock.sim_time, reschedule=True
                )
            outcome = "pivoted"
        elif move.type == ReactionCounterMoveType.GO_QUIET:
            state.dwell_multiplier *= move.dwell_multiplier
            state.signals_suppressed = state.signals_suppressed or move.suppress_signals
            index = state.next_technique_index
            if 0 <= index < len(campaign.techniques):
                self._schedule_advance(
                    state, campaign, index, self.clock.sim_time, reschedule=True
                )
            outcome = "went_quiet"
        elif move.type == ReactionCounterMoveType.ACTIVATE_TECHNIQUE:
            activate_index = technique_index(campaign, str(move.technique_id))
            if activate_index is not None:
                self._schedule_advance(
                    state, campaign, activate_index, self.clock.sim_time, reschedule=True
                )
                outcome = "activated_technique"
            else:
                state.active = False
                state.status = CampaignStatus.STALLED.value

        emitted.append(
            self._killchain_event(
                KILLCHAIN_REACTION_FIRED,
                state.current_foothold_id,
                {
                    "campaignId": campaign.id,
                    "reactionId": reaction.id,
                    "precondition": reaction.precondition.type.value,
                    "counterMove": move.type.value,
                    "outcome": outcome,
                },
            )
        )
        if outcome == "stalled":
            emitted.append(
                self._killchain_event(
                    KILLCHAIN_CAMPAIGN_STALLED,
                    state.current_foothold_id,
                    {"campaignId": campaign.id, "reactionId": reaction.id},
                )
            )
        return emitted

    def _killchain_event(
        self,
        event_type: str,
        subject_asset_id: str | None,
        payload: dict[str, object],
    ) -> DomainEventEnvelopeV1:
        """Build + record a kill-chain domain event (attacker actor, asset subject)."""
        sequence = self.world.next_sequence
        if subject_asset_id:
            subject = ActorRef(type=ActorType.ASSET, id=subject_asset_id)
        else:
            subject = ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine")
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
            subject=subject,
            payload={"schemaVersion": 1, **payload},
            trace_id=derive_trace_id(run_seed=self.configuration.seed, sequence=sequence),
        )
        self._record_event(event)
        return event

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
