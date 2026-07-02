"""Model artifact serialization and checksum."""

from __future__ import annotations

import hashlib
from pathlib import Path

import joblib
from aegis_ml.models.isolation_forest.threshold import ThresholdCalibration
from sklearn.pipeline import Pipeline


def artifact_checksum(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def save_pipeline(
    pipeline: Pipeline,
    calibration: ThresholdCalibration,
    feature_stats: dict[str, tuple[float, float]],
    path: Path,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline": pipeline,
        "calibration": calibration,
        "feature_stats": feature_stats,
    }
    joblib.dump(payload, path)
    return artifact_checksum(path)


def load_pipeline(
    path: Path,
) -> tuple[Pipeline, ThresholdCalibration, dict[str, tuple[float, float]]]:
    payload = joblib.load(path)
    if not isinstance(payload, dict):
        msg = "Invalid artifact payload structure"
        raise ValueError(msg)
    pipeline = payload["pipeline"]
    calibration = payload["calibration"]
    feature_stats = payload["feature_stats"]
    if not isinstance(pipeline, Pipeline):
        msg = "Artifact pipeline is not a sklearn Pipeline"
        raise ValueError(msg)
    if not isinstance(calibration, ThresholdCalibration):
        msg = "Artifact calibration is missing or invalid"
        raise ValueError(msg)
    return pipeline, calibration, feature_stats
