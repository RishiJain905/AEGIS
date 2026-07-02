"""Single-vector anomaly scoring."""

from __future__ import annotations

from aegis_contracts.features import FeatureVectorV1
from aegis_contracts.models import MODEL_INFERENCE_RESULT_SCHEMA_VERSION, ModelInferenceResultV1
from aegis_ml.models.artifact_store import LoadedModelArtifact
from aegis_ml.models.isolation_forest.explain import build_explanation, risk_band_for_score
from aegis_ml.models.isolation_forest.threshold import normalize_single_score, raw_decision_scores
from aegis_ml.models.isolation_forest.trainer import vectors_to_matrix


def build_deduplication_key(vector: FeatureVectorV1) -> str:
    window_start = vector.window_key.rsplit(":", 1)[-1]
    return f"{vector.provenance.run_id}:isolation-forest:{vector.entity_id}:{window_start}"


def score_vector(
    vector: FeatureVectorV1,
    artifact: LoadedModelArtifact,
    *,
    baseline_version: str | None = "1.0.0",
) -> ModelInferenceResultV1:
    matrix = vectors_to_matrix([vector])
    raw = float(raw_decision_scores(artifact.pipeline, matrix)[0])
    normalized = normalize_single_score(raw, artifact.calibration)
    threshold = artifact.manifest.threshold or artifact.calibration.threshold
    explanation = build_explanation(
        vector=vector,
        normalized_score=normalized,
        threshold=threshold,
        model_version_id=artifact.manifest.id,
        model_semantic_version=artifact.manifest.semantic_version,
        feature_stats=artifact.feature_stats,
        baseline_version=baseline_version,
    )
    risk_band = risk_band_for_score(
        normalized,
        threshold=threshold,
        elevated_threshold=artifact.calibration.elevated_threshold,
    )
    source_ids = vector.provenance.source_event_ids
    source_event_id = source_ids[-1] if source_ids else None
    return ModelInferenceResultV1(
        schema_version=MODEL_INFERENCE_RESULT_SCHEMA_VERSION,
        entity_id=vector.entity_id,  # type: ignore[arg-type]
        score=normalized,
        threshold=threshold,
        risk_band=risk_band,
        explanation=explanation,
        deduplication_key=build_deduplication_key(vector),
        source_event_id=source_event_id,
        is_anomaly=normalized >= threshold,
    )
