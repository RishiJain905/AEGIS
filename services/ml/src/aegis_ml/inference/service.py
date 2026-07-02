"""Anomaly detection inference orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.models import (
    MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION,
    ModelInferenceResultV1,
    ModelScoreResponseV1,
)
from aegis_ml.features import compute_features_from_events
from aegis_ml.inference.batch import score_vectors
from aegis_ml.inference.fallback import FallbackState, fallback_from_exception
from aegis_ml.inference.loader import get_loaded_model
from aegis_ml.models.artifact_store import LoadedModelArtifact


@dataclass
class InferencePipelineResult:
    results: list[ModelInferenceResultV1] = field(default_factory=list)
    fallback: FallbackState = field(default_factory=lambda: FallbackState(active=False))
    artifact: LoadedModelArtifact | None = None


def _checksum_results(results: list[ModelInferenceResultV1]) -> str:
    payload = [item.model_dump(mode="json", by_alias=True) for item in results]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def run_inference_for_events(
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
    existing_dedup_keys: set[str] | None = None,
) -> InferencePipelineResult:
    feature_result = compute_features_from_events(run_id=run_id, events=events)
    dedup_keys = set(existing_dedup_keys or set())
    try:
        artifact = get_loaded_model()
    except Exception as exc:
        return InferencePipelineResult(results=[], fallback=fallback_from_exception(exc))

    scored = score_vectors(feature_result.vectors, artifact)
    accepted = [item for item in scored if item.deduplication_key not in dedup_keys]
    return InferencePipelineResult(
        results=accepted,
        fallback=FallbackState(active=False),
        artifact=artifact,
    )


def to_response(
    *,
    run_id: str,
    pipeline_result: InferencePipelineResult,
    alerts_persisted: int = 0,
    scores_suppressed: int = 0,
) -> ModelScoreResponseV1:
    anomalies = [item for item in pipeline_result.results if item.is_anomaly]
    return ModelScoreResponseV1(
        schema_version=MODEL_EVALUATE_RESPONSE_SCHEMA_VERSION,
        run_id=run_id,
        model_version_id=pipeline_result.artifact.manifest.id if pipeline_result.artifact else None,
        scores_computed=len(pipeline_result.results),
        anomalies_detected=len(anomalies),
        alerts_persisted=alerts_persisted,
        scores_suppressed=scores_suppressed,
        fallback_active=pipeline_result.fallback.active,
        fallback_reason=pipeline_result.fallback.reason,
        results=pipeline_result.results,
        deterministic_checksum=_checksum_results(pipeline_result.results),
    )
