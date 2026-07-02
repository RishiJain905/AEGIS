"""Phase 14 feature pipeline package."""

from aegis_ml.features.dataset_builder import build_dataset_from_events
from aegis_ml.features.engine import (
    FeatureTransformEngine,
    FeatureTransformResult,
    build_compute_response,
    checksum_vectors,
    compute_features_from_events,
)
from aegis_ml.features.parity import run_offline_online_parity
from aegis_ml.features.schema_registry import FEATURE_SCHEMA_MANIFEST_V1

__all__ = [
    "FEATURE_SCHEMA_MANIFEST_V1",
    "FeatureTransformEngine",
    "FeatureTransformResult",
    "build_compute_response",
    "build_dataset_from_events",
    "checksum_vectors",
    "compute_features_from_events",
    "run_offline_online_parity",
]
