"""Phase 15 statistical baseline package."""

from aegis_ml.baselines.calibration import calibrate_baselines_from_vectors
from aegis_ml.baselines.scorer import score_feature_against_baseline
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, TRAINING_SEEDS
from aegis_ml.baselines.store import (
    baseline_checksum,
    load_baseline,
    load_baseline_manifest,
    save_baseline,
)

__all__ = [
    "HOLDOUT_SEEDS",
    "TRAINING_SEEDS",
    "baseline_checksum",
    "calibrate_baselines_from_vectors",
    "load_baseline",
    "load_baseline_manifest",
    "save_baseline",
    "score_feature_against_baseline",
]
