"""Allowlisted behavior plugin execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

from aegis_simulation_domain.ids import derive_event_id, derive_trace_id
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.world_state import GeneratorState, WorldState


@dataclass(slots=True)
class HandlerResult:
    events: list[DomainEventEnvelopeV1]
    reschedule: datetime | None = None


def _recorded_at(recorded_at_epoch: datetime, sequence: int) -> datetime:
    return recorded_at_epoch + timedelta(milliseconds=sequence)


def _build_envelope(
    *,
    run_id: str,
    run_seed: int,
    sequence: int,
    event_type: str,
    sim_time: datetime,
    recorded_at_epoch: datetime,
    actor: ActorRef,
    subject: ActorRef,
    payload: dict[str, Any],
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=derive_event_id(run_seed=run_seed, sequence=sequence, event_type=event_type),
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=_recorded_at(recorded_at_epoch, sequence),
        actor=actor,
        subject=subject,
        payload={"schemaVersion": 1, **payload},
        trace_id=derive_trace_id(run_seed=run_seed, sequence=sequence),
    )


def execute_plugin(
    *,
    plugin_id: str,
    config: dict[str, Any],
    target_asset_id: str | None,
    world: WorldState,
    run_id: str,
    run_seed: int,
    sequence: int,
    sim_time: datetime,
    recorded_at_epoch: datetime,
    rng: SeededRandomStreams,
    generator: GeneratorState | None = None,
) -> HandlerResult:
    system_actor = ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine")
    emitted: list[DomainEventEnvelopeV1] = []
    next_sequence = sequence

    if plugin_id == "telemetry.auth_attempt":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.auth_attempt:{asset_id}")
        failure_rate = float(config.get("failureRate", config.get("failure_rate", 0.1)))
        is_failure = stream.random() < failure_rate
        event_type = (
            "telemetry.authentication.failed"
            if is_failure
            else "telemetry.authentication.succeeded"
        )
        subject = ActorRef(type=ActorType.ASSET, id=asset_id)
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type=event_type,
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=subject,
                payload={"assetId": asset_id, "outcome": "failed" if is_failure else "succeeded"},
            )
        )
        next_sequence += 1
        reschedule = None
        if generator is not None:
            generator.next_sim_time = sim_time + timedelta(seconds=generator.interval_sim_seconds)
            reschedule = generator.next_sim_time
        return HandlerResult(events=emitted, reschedule=reschedule)

    if plugin_id == "telemetry.api_request":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.api_request:{asset_id}")
        error_rate = float(config.get("errorRate", config.get("error_rate", 0.05)))
        is_error = stream.random() < error_rate
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.api.request",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={"assetId": asset_id, "statusCode": 500 if is_error else 200},
            )
        )
        reschedule = None
        if generator is not None:
            generator.next_sim_time = sim_time + timedelta(seconds=generator.interval_sim_seconds)
            reschedule = generator.next_sim_time
        return HandlerResult(events=emitted, reschedule=reschedule)

    if plugin_id == "telemetry.network_flow":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.network.connection",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={
                    "assetId": asset_id,
                    "protocol": str(config.get("protocol", "tcp")),
                    "bytes": int(
                        config.get("bytesPerInterval", config.get("bytes_per_interval", 1024))
                    ),
                },
            )
        )
        reschedule = None
        if generator is not None:
            generator.next_sim_time = sim_time + timedelta(seconds=generator.interval_sim_seconds)
            reschedule = generator.next_sim_time
        return HandlerResult(events=emitted, reschedule=reschedule)

    if plugin_id == "telemetry.health_check":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.health_check:{asset_id}")
        healthy_probability = float(
            config.get("healthyProbability", config.get("healthy_probability", 0.95))
        )
        healthy = stream.random() < healthy_probability
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.health.check",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={"assetId": asset_id, "healthy": healthy},
            )
        )
        reschedule = None
        if generator is not None:
            generator.next_sim_time = sim_time + timedelta(seconds=generator.interval_sim_seconds)
            reschedule = generator.next_sim_time
        return HandlerResult(events=emitted, reschedule=reschedule)

    if plugin_id == "effect.set_asset_status":
        status = str(config.get("status", "unknown"))
        asset_id = str(config.get("assetId", target_asset_id or "asset:svc-auth-service"))
        asset = world.assets.get(asset_id)
        if asset is not None:
            asset.status = status
            asset.revision += 1
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="sim.asset.status_changed",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={"assetId": asset_id, "status": status},
            )
        )
        return HandlerResult(events=emitted)

    if plugin_id == "effect.adjust_relationship_confidence":
        edge_id = str(config.get("edgeId", ""))
        delta = float(config.get("delta", 0.0))
        relationship = world.relationships.get(edge_id)
        if relationship is not None:
            relationship.confidence = max(0.0, min(1.0, relationship.confidence + delta))
            relationship.revision += 1
        return HandlerResult(events=emitted)

    if plugin_id == "branch.seed_selector":
        branch_group = str(config.get("branchGroup", config.get("branch_group", "default")))
        stream = rng.stream(f"branch.seed_selector:{branch_group}")
        selected = f"branch-{int(stream.random() * 1000)}"
        world.selected_branches[branch_group] = selected
        return HandlerResult(events=emitted)

    msg = f"Unknown plugin: {plugin_id}"
    raise ValueError(msg)
