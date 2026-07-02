"""Promote alert candidates to authoritative alerts and domain events."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, AlertV1, DomainEventEnvelopeV1
from aegis_contracts.detection import AlertCandidateV1
from aegis_contracts.versioning import ALERT_SCHEMA_VERSION, DOMAIN_EVENT_SCHEMA_VERSION


def deterministic_alert_id(deduplication_key: str) -> str:
    digest = hashlib.sha256(deduplication_key.encode("utf-8")).hexdigest()[:20]
    return f"alert:det-{digest}"


def deterministic_event_id(deduplication_key: str) -> str:
    digest = hashlib.sha256(f"evt:{deduplication_key}".encode()).hexdigest()
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    chars = [alphabet[int(digest[index * 2 : index * 2 + 2], 16) % 32] for index in range(26)]
    return f"evt_{''.join(chars)}"


def candidate_to_alert(candidate: AlertCandidateV1) -> AlertV1:
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id=deterministic_alert_id(candidate.deduplication_key),
        run_id=candidate.run_id,
        title=candidate.title,
        severity=candidate.severity,
        source_event_id=candidate.source_event_id,
        asset_id=candidate.entity_id,
        created_at=datetime.now(tz=UTC),
        confidence=candidate.confidence,
        detector_id=candidate.detector_id,
        detector_version=candidate.detector_version,
        rule_id=candidate.rule_id,
        rule_version=candidate.rule_version,
        explanation=candidate.explanation,
        evidence=candidate.evidence,
        deduplication_key=candidate.deduplication_key,
    )


def build_alert_created_event(
    alert: AlertV1,
    *,
    sequence: int,
    sim_time: datetime,
    trace_id: str,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=deterministic_event_id(alert.deduplication_key or alert.id),
        run_id=alert.run_id,
        sequence=sequence,
        type="alert.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(tz=UTC),
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:detection-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=alert.asset_id),
        payload=alert.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
        causation_id=alert.source_event_id,
        correlation_id=None,
    )
