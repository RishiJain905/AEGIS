"""Training reproducibility tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_ml.models.isolation_forest.train import train_isolation_forest


@pytest.fixture(scope="module")
def trained_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    output = tmp_path_factory.mktemp("train-a")
    result = train_isolation_forest(output_dir=output, steps=120)
    return result.artifact_path, result.artifact_checksum


def test_training_reproduces_checksum(trained_artifacts: tuple[Path, str], tmp_path: Path) -> None:
    _, first_checksum = trained_artifacts
    second = train_isolation_forest(output_dir=tmp_path / "train-b", steps=120)
    assert second.artifact_checksum == first_checksum
