"""Score normalization and threshold calibration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.pipeline import Pipeline

SCORE_SEMANTICS = (
    "Higher normalized score indicates greater anomaly likelihood. "
    "Raw sklearn decision_function is negated and min-max scaled to [0,1] "
    "using training-set bounds."
)


@dataclass(frozen=True)
class ThresholdCalibration:
    threshold: float
    elevated_threshold: float
    score_min: float
    score_max: float


def raw_decision_scores(pipeline: Pipeline, matrix: np.ndarray) -> np.ndarray:
    scaled = pipeline.named_steps["scaler"].transform(matrix)
    scores = pipeline.named_steps["model"].decision_function(scaled)
    return np.asarray(scores, dtype=np.float64)


def normalize_scores(
    raw_scores: np.ndarray,
    *,
    score_min: float,
    score_max: float,
) -> np.ndarray:
    span = score_max - score_min
    if span <= 1e-12:
        return np.zeros_like(raw_scores)
    inverted = -raw_scores
    normalized = (inverted - score_min) / span
    return np.clip(normalized, 0.0, 1.0)


def calibrate_threshold(
    pipeline: Pipeline,
    training_matrix: np.ndarray,
    *,
    contamination: float = 0.05,
) -> ThresholdCalibration:
    raw = raw_decision_scores(pipeline, training_matrix)
    inverted = -raw
    score_min = float(np.min(inverted))
    score_max = float(np.max(inverted))
    normalized = normalize_scores(raw, score_min=score_min, score_max=score_max)
    percentile = max(0.0, min(1.0, 1.0 - contamination))
    threshold = float(np.quantile(normalized, percentile))
    elevated = float(np.quantile(normalized, max(0.0, percentile - 0.15)))
    return ThresholdCalibration(
        threshold=threshold,
        elevated_threshold=elevated,
        score_min=score_min,
        score_max=score_max,
    )


def normalize_single_score(
    raw_score: float,
    calibration: ThresholdCalibration,
) -> float:
    return float(
        normalize_scores(
            np.array([raw_score]),
            score_min=calibration.score_min,
            score_max=calibration.score_max,
        )[0]
    )
