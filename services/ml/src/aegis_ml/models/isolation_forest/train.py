"""Isolation Forest training orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aegis_contracts.features import FeatureVectorV1
from aegis_ml.baselines.splits import GOLDEN_STEPS, TRAINING_SEEDS
from aegis_ml.features import compute_features_from_events
from aegis_ml.models.artifact_store import (
    ARTIFACT_FILENAME,
    DEFAULT_MODEL_DIR,
    save_manifest_files,
)
from aegis_ml.models.isolation_forest.manifest import (
    build_model_manifest,
    build_training_run_manifest,
)
from aegis_ml.models.isolation_forest.pipeline import (
    build_isolation_forest_pipeline,
    default_hyperparameters,
)
from aegis_ml.models.isolation_forest.serialize import save_pipeline
from aegis_ml.models.isolation_forest.threshold import calibrate_threshold
from aegis_ml.models.isolation_forest.trainer import compute_feature_statistics, vectors_to_matrix
from aegis_ml.training.simulation_helpers import run_scenario_events


@dataclass(frozen=True)
class TrainingResult:
    manifest_path: Path
    artifact_path: Path
    training_run_path: Path
    vector_count: int
    artifact_checksum: str
    threshold: float


def collect_training_vectors(
    *, steps: int = GOLDEN_STEPS
) -> tuple[list[FeatureVectorV1], list[str]]:
    all_vectors: list[FeatureVectorV1] = []
    dataset_ids: list[str] = []
    for seed in TRAINING_SEEDS:
        run_id, events = run_scenario_events(seed=seed, steps=steps)
        result = compute_features_from_events(run_id=run_id, events=events)
        all_vectors.extend(result.vectors)
        dataset_ids.append(f"dataset:seed-{seed}")
    return all_vectors, dataset_ids


def train_isolation_forest(
    *,
    output_dir: Path = DEFAULT_MODEL_DIR,
    steps: int = GOLDEN_STEPS,
) -> TrainingResult:
    vectors, dataset_ids = collect_training_vectors(steps=steps)
    matrix = vectors_to_matrix(vectors)
    hyperparams = default_hyperparameters()
    pipeline = build_isolation_forest_pipeline(
        random_state=int(hyperparams["random_state"]),
        n_estimators=int(hyperparams["n_estimators"]),
        contamination=float(hyperparams["contamination"]),
    )
    pipeline.fit(matrix)
    calibration = calibrate_threshold(
        pipeline,
        matrix,
        contamination=float(hyperparams["contamination"]),
    )
    feature_stats = compute_feature_statistics(vectors)

    artifact_path = output_dir / ARTIFACT_FILENAME
    checksum = save_pipeline(pipeline, calibration, feature_stats, artifact_path)

    training_run = build_training_run_manifest(vector_count=len(vectors), dataset_ids=dataset_ids)
    manifest = build_model_manifest(
        artifact_checksum=checksum,
        calibration=calibration,
        evaluation_metrics={
            "trainingVectorCount": len(vectors),
            "threshold": calibration.threshold,
        },
        dataset_ids=dataset_ids,
    )
    save_manifest_files(manifest, training_run, model_dir=output_dir)

    return TrainingResult(
        manifest_path=output_dir / "manifest.json",
        artifact_path=artifact_path,
        training_run_path=output_dir / "training_run.json",
        vector_count=len(vectors),
        artifact_checksum=checksum,
        threshold=calibration.threshold,
    )


def training_result_to_json(result: TrainingResult) -> dict[str, object]:
    return {
        "manifestPath": str(result.manifest_path),
        "artifactPath": str(result.artifact_path),
        "trainingRunPath": str(result.training_run_path),
        "vectorCount": result.vector_count,
        "artifactChecksum": result.artifact_checksum,
        "threshold": result.threshold,
    }
