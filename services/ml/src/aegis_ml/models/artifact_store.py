"""Filesystem model artifact storage with verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aegis_contracts.entities import ModelManifestV1
from aegis_contracts.models import (
    ModelApprovalStatus,
    ModelVerifyArtifactResponseV1,
    TrainingRunManifestV1,
)
from aegis_contracts.versioning import (
    FEATURE_SCHEMA_VERSION,
    MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
)
from aegis_ml.models.errors import ModelErrorCode
from aegis_ml.models.isolation_forest.serialize import artifact_checksum, load_pipeline
from aegis_ml.models.isolation_forest.threshold import ThresholdCalibration
from sklearn.pipeline import Pipeline

DEFAULT_MODEL_DIR = Path("models/manifests/isolation-forest-v1")
ARTIFACT_FILENAME = "artifact.joblib"
MANIFEST_FILENAME = "manifest.json"
TRAINING_RUN_FILENAME = "training_run.json"


@dataclass(frozen=True)
class LoadedModelArtifact:
    manifest: ModelManifestV1
    pipeline: Pipeline
    calibration: ThresholdCalibration
    feature_stats: dict[str, tuple[float, float]]
    training_run: TrainingRunManifestV1 | None


class ModelArtifactError(Exception):
    def __init__(self, code: ModelErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_manifest(*, model_dir: Path = DEFAULT_MODEL_DIR) -> ModelManifestV1:
    manifest_path = model_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ModelArtifactError(
            ModelErrorCode.ARTIFACT_NOT_FOUND,
            f"Manifest not found: {manifest_path}",
        )
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ModelManifestV1.model_validate(raw)


def load_training_run(*, model_dir: Path = DEFAULT_MODEL_DIR) -> TrainingRunManifestV1 | None:
    path = model_dir / TRAINING_RUN_FILENAME
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TrainingRunManifestV1.model_validate(raw)


def verify_artifact(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    manifest_path: Path | None = None,
    artifact_path: Path | None = None,
) -> ModelVerifyArtifactResponseV1:
    resolved_manifest_path = manifest_path or (model_dir / MANIFEST_FILENAME)
    resolved_artifact_path = artifact_path or (model_dir / ARTIFACT_FILENAME)

    if not resolved_manifest_path.exists():
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=False,
            error_code=ModelErrorCode.ARTIFACT_NOT_FOUND.value,
            error_message=f"Manifest not found: {resolved_manifest_path}",
        )

    try:
        manifest = ModelManifestV1.model_validate(
            json.loads(resolved_manifest_path.read_text(encoding="utf-8"))
        )
    except Exception as exc:
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=False,
            error_code=ModelErrorCode.MANIFEST_INVALID.value,
            error_message=str(exc),
        )

    schema_compatible = manifest.feature_schema_version == FEATURE_SCHEMA_VERSION
    approval = manifest.approval_status or ModelApprovalStatus.APPROVED.value
    if approval == ModelApprovalStatus.REJECTED.value:
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=schema_compatible,
            approval_status=ModelApprovalStatus.REJECTED,
            error_code=ModelErrorCode.APPROVAL_REJECTED.value,
            error_message="Model approval status is rejected",
        )

    if not schema_compatible:
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=False,
            approval_status=ModelApprovalStatus(approval),
            error_code=ModelErrorCode.SCHEMA_INCOMPATIBLE.value,
            error_message=(
                f"Feature schema version {manifest.feature_schema_version} "
                f"!= required {FEATURE_SCHEMA_VERSION}"
            ),
        )

    if not resolved_artifact_path.exists():
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=True,
            approval_status=ModelApprovalStatus(approval),
            error_code=ModelErrorCode.ARTIFACT_NOT_FOUND.value,
            error_message=f"Artifact not found: {resolved_artifact_path}",
        )

    checksum_match = artifact_checksum(resolved_artifact_path) == manifest.artifact_checksum
    if not checksum_match:
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=False,
            schema_compatible=True,
            approval_status=ModelApprovalStatus(approval),
            error_code=ModelErrorCode.CHECKSUM_MISMATCH.value,
            error_message="Artifact checksum does not match manifest",
        )

    try:
        load_pipeline(resolved_artifact_path)
    except Exception as exc:
        return ModelVerifyArtifactResponseV1(
            schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
            valid=False,
            checksum_match=True,
            schema_compatible=True,
            approval_status=ModelApprovalStatus(approval),
            error_code=ModelErrorCode.LOAD_FAILED.value,
            error_message=str(exc),
        )

    return ModelVerifyArtifactResponseV1(
        schema_version=MODEL_VERIFY_ARTIFACT_RESPONSE_SCHEMA_VERSION,
        valid=True,
        checksum_match=True,
        schema_compatible=True,
        approval_status=ModelApprovalStatus(approval),
    )


def load_verified_artifact(*, model_dir: Path = DEFAULT_MODEL_DIR) -> LoadedModelArtifact:
    verification = verify_artifact(model_dir=model_dir)
    if not verification.valid:
        raise ModelArtifactError(
            ModelErrorCode(verification.error_code or ModelErrorCode.LOAD_FAILED.value),
            verification.error_message or "Artifact verification failed",
        )
    manifest = load_manifest(model_dir=model_dir)
    pipeline, calibration, feature_stats = load_pipeline(model_dir / ARTIFACT_FILENAME)
    return LoadedModelArtifact(
        manifest=manifest,
        pipeline=pipeline,
        calibration=calibration,
        feature_stats=feature_stats,
        training_run=load_training_run(model_dir=model_dir),
    )


def save_manifest_files(
    manifest: ModelManifestV1,
    training_run: TrainingRunManifestV1,
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    (model_dir / TRAINING_RUN_FILENAME).write_text(
        json.dumps(training_run.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
