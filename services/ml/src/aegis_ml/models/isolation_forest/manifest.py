"""Model manifest construction."""

from __future__ import annotations

from datetime import UTC, datetime

import sklearn
from aegis_contracts.entities import ModelManifestV1
from aegis_contracts.models import (
    TRAINING_RUN_MANIFEST_SCHEMA_VERSION,
    ModelApprovalStatus,
    TrainingRunManifestV1,
)
from aegis_contracts.versioning import (
    FEATURE_SCHEMA_VERSION,
    MODEL_MANIFEST_SCHEMA_VERSION,
    WORKSPACE_VERSION,
)
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, SILENT_RELAY_SCENARIO_ID, TRAINING_SEEDS
from aegis_ml.models.isolation_forest.pipeline import default_hyperparameters
from aegis_ml.models.isolation_forest.threshold import SCORE_SEMANTICS, ThresholdCalibration

MODEL_ID = "mdl_01ARZ3NDEKTSV4RRFFQ69G5FB1"
SEMANTIC_VERSION = "1.0.0"
TRAINING_RUN_ID = "train-isolation-forest-v1"
ARTIFACT_OBJECT_KEY = "models/manifests/isolation-forest-v1/artifact.joblib"


def build_training_run_manifest(
    *,
    vector_count: int,
    dataset_ids: list[str],
) -> TrainingRunManifestV1:
    return TrainingRunManifestV1(
        schema_version=TRAINING_RUN_MANIFEST_SCHEMA_VERSION,
        training_run_id=TRAINING_RUN_ID,
        scenario_id=SILENT_RELAY_SCENARIO_ID,
        training_seeds=list(TRAINING_SEEDS),
        holdout_seeds=list(HOLDOUT_SEEDS),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        dataset_ids=dataset_ids,
        hyperparameters=default_hyperparameters(),
        random_seed=42,
        code_revision=WORKSPACE_VERSION,
        sklearn_version=sklearn.__version__,
        vector_count=vector_count,
        split_policy="scenario-seed-holdout",
        created_at=datetime.now(tz=UTC),
    )


def build_model_manifest(
    *,
    artifact_checksum: str,
    calibration: ThresholdCalibration,
    evaluation_metrics: dict[str, float | int | str | None],
    dataset_ids: list[str],
) -> ModelManifestV1:
    return ModelManifestV1(
        schema_version=MODEL_MANIFEST_SCHEMA_VERSION,
        id=MODEL_ID,  # type: ignore[arg-type]
        semantic_version=SEMANTIC_VERSION,
        algorithm="isolation_forest",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        artifact_checksum=artifact_checksum,
        artifact_object_key=ARTIFACT_OBJECT_KEY,
        evaluation_metrics=evaluation_metrics,
        known_limitations=[
            "Trained on synthetic Operation Silent Relay telemetry only",
            "Unsupervised; holdout evaluation uses evaluation-only root-cause labels",
            "Advisory scores only — no automated containment",
        ],
        created_at=datetime.now(tz=UTC),
        hyperparameters=default_hyperparameters(),
        threshold=calibration.threshold,
        risk_band_thresholds={
            "elevated": calibration.elevated_threshold,
            "high": calibration.threshold,
        },
        training_run_id=TRAINING_RUN_ID,
        code_revision=WORKSPACE_VERSION,
        sklearn_version=sklearn.__version__,
        dataset_ids=dataset_ids,
        approval_status=ModelApprovalStatus.APPROVED.value,
        score_semantics=SCORE_SEMANTICS,
    )
