"""Artifact verification fail-closed tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_ml.models.artifact_store import DEFAULT_MODEL_DIR, verify_artifact
from aegis_ml.models.isolation_forest.train import train_isolation_forest


@pytest.fixture(scope="module", autouse=True)
def ensure_trained_model() -> None:
    if not (DEFAULT_MODEL_DIR / "manifest.json").exists():
        train_isolation_forest(output_dir=DEFAULT_MODEL_DIR, steps=120)


def test_valid_artifact_passes_verification() -> None:
    result = verify_artifact(model_dir=DEFAULT_MODEL_DIR)
    assert result.valid is True
    assert result.checksum_match is True
    assert result.schema_compatible is True


def test_corrupt_artifact_rejected(tmp_path: Path) -> None:
    manifest = DEFAULT_MODEL_DIR / "manifest.json"
    corrupt = tmp_path / "corrupt.joblib"
    corrupt.write_bytes(b"not-a-valid-artifact")
    result = verify_artifact(
        model_dir=DEFAULT_MODEL_DIR,
        manifest_path=manifest,
        artifact_path=corrupt,
    )
    assert result.valid is False
    assert result.checksum_match is False


def test_missing_artifact_rejected(tmp_path: Path) -> None:
    manifest = DEFAULT_MODEL_DIR / "manifest.json"
    missing = tmp_path / "missing.joblib"
    result = verify_artifact(
        model_dir=DEFAULT_MODEL_DIR,
        manifest_path=manifest,
        artifact_path=missing,
    )
    assert result.valid is False
    assert result.error_code == "MODEL_ARTIFACT_NOT_FOUND"
