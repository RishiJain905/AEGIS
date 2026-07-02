"""Promote model inference results to authoritative alerts and events."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, AlertV1, DomainEventEnvelopeV1, ModelScoreV1
from aegis_contracts.detection import AlertEvidenceV1
from aegis_contracts.models import ModelInferenceResultV1
from aegis_contracts.versioning import (
    ALERT_SCHEMA_VERSION,
    DOMAIN_EVENT_SCHEMA_VERSION,
    MODEL_SCORE_SCHEMA_VERSION,
)

from aegis_incidents.promotion import deterministic_alert_id, deterministic_event_id


def inference_to_alert(result: ModelInferenceResultV1, *, run_id: str) -> AlertV1:
    source_event_id = result.source_event_id or deterministic_event_id(result.deduplication_key)
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id=deterministic_alert_id(result.deduplication_key),
        run_id=run_id,
        title=f"Isolation Forest anomaly on {result.entity_id}",
        severity="high" if result.risk_band.value == "high" else "medium",
        source_event_id=source_event_id,
        asset_id=result.entity_id,
        created_at=datetime.now(tz=UTC),
        confidence=result.score,
        detector_id="isolation-forest",
        detector_version=result.explanation.model_semantic_version,
        explanation=None,
        anomaly_explanation=result.explanation.model_dump(mode="json", by_alias=True),
        model_version_id=result.explanation.model_version_id,
        evidence=AlertEvidenceV1(
            feature_schema_version=1,
            feature_values=result.explanation.feature_contributions,
            source_event_ids=[source_event_id] if result.source_event_id else [],
            window_key=result.explanation.source_window.window_start_epoch.__str__(),
            sequence_start=0,
            sequence_end=0,
            sim_time_start=result.explanation.source_window.sim_time_start,
            sim_time_end=result.explanation.source_window.sim_time_end,
        ),
        deduplication_key=result.deduplication_key,
    )


def inference_to_model_score(result: ModelInferenceResultV1) -> ModelScoreV1:
    return ModelScoreV1(
        schema_version=MODEL_SCORE_SCHEMA_VERSION,
        model_version_id=result.explanation.model_version_id,
        entity_id=result.entity_id,
        score=result.score,
        risk_band=result.risk_band.value,
        feature_schema_version=1,
        explanation=result.explanation.model_dump(mode="json", by_alias=True),
        scored_at=datetime.now(tz=UTC),
        source_event_id=result.source_event_id,
    )


def build_model_score_recorded_event(
    score: ModelScoreV1,
    *,
    run_id: str,
    sequence: int,
    sim_time: datetime,
    trace_id: str,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=deterministic_event_id(f"model-score:{score.entity_id}:{sequence}"),
        run_id=run_id,
        sequence=sequence,
        type="model.score.recorded",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(tz=UTC),
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:anomaly-model"),
        subject=ActorRef(type=ActorType.ASSET, id=score.entity_id),
        payload=score.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
        causation_id=score.source_event_id,
        correlation_id=None,
    )


def build_model_alert_created_event(
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
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:anomaly-model"),
        subject=ActorRef(type=ActorType.ASSET, id=alert.asset_id),
        payload=alert.model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
        causation_id=alert.source_event_id,
        correlation_id=None,
    )
