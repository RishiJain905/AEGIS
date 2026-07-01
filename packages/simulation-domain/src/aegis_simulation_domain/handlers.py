"""Allowlisted behavior plugin execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1

from aegis_simulation_domain.branch_selection import select_weighted_branch
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


def _reschedule_generator(
    generator: GeneratorState | None,
    sim_time: datetime,
) -> datetime | None:
    if generator is None:
        return None
    generator.next_sim_time = sim_time + timedelta(seconds=generator.interval_sim_seconds)
    return generator.next_sim_time


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
    manifest: ScenarioManifestV1 | None = None,
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
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

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
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

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
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

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
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

    if plugin_id == "telemetry.database_query":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.database_query:{asset_id}")
        anomaly_rate = float(config.get("anomalyRate", config.get("anomaly_rate", 0.02)))
        anomalous = stream.random() < anomaly_rate
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.database.query",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={
                    "assetId": asset_id,
                    "queryCount": int(
                        config.get("queriesPerInterval", config.get("queries_per_interval", 5))
                    ),
                    "anomalous": anomalous,
                },
            )
        )
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

    if plugin_id == "telemetry.deployment_event":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.deployment_event:{asset_id}")
        failure_rate = float(config.get("failureRate", config.get("failure_rate", 0.05)))
        failed = stream.random() < failure_rate
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.deployment.event",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={
                    "assetId": asset_id,
                    "deploymentCount": int(
                        config.get(
                            "deploymentsPerInterval",
                            config.get("deployments_per_interval", 1),
                        )
                    ),
                    "failed": failed,
                },
            )
        )
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

    if plugin_id == "telemetry.process_activity":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.process_activity:{asset_id}")
        suspicious_rate = float(
            config.get("suspiciousRate", config.get("suspicious_rate", 0.03))
        )
        suspicious = stream.random() < suspicious_rate
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.process.activity",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={
                    "assetId": asset_id,
                    "eventCount": int(
                        config.get("eventsPerInterval", config.get("events_per_interval", 10))
                    ),
                    "suspicious": suspicious,
                },
            )
        )
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

    if plugin_id == "telemetry.ai_inference":
        asset_id = target_asset_id or (generator.target_asset_id if generator else "asset:unknown")
        stream = rng.stream(f"telemetry.ai_inference:{asset_id}")
        anomaly_rate = float(config.get("anomalyRate", config.get("anomaly_rate", 0.02)))
        anomalous = stream.random() < anomaly_rate
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="telemetry.ai.inference",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.ASSET, id=asset_id),
                payload={
                    "assetId": asset_id,
                    "inferenceCount": int(
                        config.get(
                            "inferencesPerInterval",
                            config.get("inferences_per_interval", 8),
                        )
                    ),
                    "anomalous": anomalous,
                },
            )
        )
        return HandlerResult(events=emitted, reschedule=_reschedule_generator(generator, sim_time))

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
        edge_id = str(config.get("edgeId", config.get("edge_id", "")))
        delta = float(config.get("delta", 0.0))
        relationship = world.relationships.get(edge_id)
        if relationship is not None:
            relationship.confidence = max(0.0, min(1.0, relationship.confidence + delta))
            relationship.revision += 1
        return HandlerResult(events=emitted)

    if plugin_id == "branch.seed_selector":
        branch_group = str(config.get("branchGroup", config.get("branch_group", "default")))
        candidate_ids = list(
            config.get("candidateBranchIds", config.get("candidate_branch_ids", []))
        )
        stream = rng.stream(f"branch.seed_selector:{branch_group}")
        selected: str | None = None
        if manifest is not None:
            selected = select_weighted_branch(
                manifest.branches,
                branch_group=branch_group,
                candidate_branch_ids=candidate_ids,
                stream=stream,
            )
        if selected is None:
            selected = f"branch-{int(stream.random() * 1000)}"
        world.selected_branches[branch_group] = selected
        emitted.append(
            _build_envelope(
                run_id=run_id,
                run_seed=run_seed,
                sequence=next_sequence,
                event_type="sim.branch.selected",
                sim_time=sim_time,
                recorded_at_epoch=recorded_at_epoch,
                actor=system_actor,
                subject=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
                payload={"branchGroup": branch_group, "branchId": selected},
            )
        )
        return HandlerResult(events=emitted)

    msg = f"Unknown plugin: {plugin_id}"
    raise ValueError(msg)
