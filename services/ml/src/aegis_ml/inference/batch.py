"""Batch scoring for feature vectors."""

from __future__ import annotations

from aegis_contracts.features import FeatureVectorV1
from aegis_contracts.models import ModelInferenceResultV1
from aegis_ml.inference.scorer import score_vector
from aegis_ml.models.artifact_store import LoadedModelArtifact


def score_vectors(
    vectors: list[FeatureVectorV1],
    artifact: LoadedModelArtifact,
    *,
    baseline_version: str | None = "1.0.0",
) -> list[ModelInferenceResultV1]:
    return [score_vector(vector, artifact, baseline_version=baseline_version) for vector in vectors]
