"""Promote graph risk results to authoritative events."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.risk import AssetRiskScoreV1, RiskProjectionDeltaV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

from aegis_incidents.promotion import deterministic_event_id


def risk_dedup_key(run_id: str, asset_id: str, sequence: int) -> str:
    return f"{run_id}:graph-risk:{asset_id}:{sequence}"


def build_risk_score_computed_event(
    score: AssetRiskScoreV1,
    *,
    sequence: int,
    trace_id: str,
) -> DomainEventEnvelopeV1:
    dedup = risk_dedup_key(score.run_id, score.asset_id, sequence)
    return DomainEventEnvelopeV1(
        event_id=deterministic_event_id(dedup),
        run_id=score.run_id,
        sequence=sequence,
        type="risk.score.computed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=score.sim_time,
        recorded_at=datetime.now(tz=UTC),
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:graph-risk-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=score.asset_id),
        payload=score.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
        causation_id=None,
        correlation_id=None,
    )


def build_risk_projection_updated_event(
    delta: RiskProjectionDeltaV1,
    *,
    sequence: int,
    sim_time: datetime,
    trace_id: str,
) -> DomainEventEnvelopeV1:
    dedup = f"{delta.run_id}:risk-projection:{sequence}"
    return DomainEventEnvelopeV1(
        event_id=deterministic_event_id(dedup),
        run_id=delta.run_id,
        sequence=sequence,
        type="risk.projection.updated",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(tz=UTC),
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:graph-risk-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=delta.node_updates[0].asset_id),
        payload=delta.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
        causation_id=None,
        correlation_id=None,
    )


def projection_checksum(delta: RiskProjectionDeltaV1) -> str:
    digest = hashlib.sha256(
        delta.model_dump_json(by_alias=True).encode("utf-8"),
    ).hexdigest()
    return f"sha256:{digest}"
