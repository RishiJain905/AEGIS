"""Tests for Phase 16 model contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.models import (
    AnomalyExplanationV1,
    ModelArtifactReferenceV1,
    TrainingRunManifestV1,
)
from aegis_contracts.parsing import parse_contract


@pytest.mark.parametrize(
    "fixture_name,model",
    [
        ("anomaly_explanation_v1", AnomalyExplanationV1),
        ("training_run_manifest_v1", TrainingRunManifestV1),
        ("model_artifact_reference_v1", ModelArtifactReferenceV1),
    ],
)
def test_model_contract_fixtures(fixture_name: str, model: type) -> None:
    path = Path(f"tests/contract/fixtures/valid/{fixture_name}.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = parse_contract(model, payload)
    assert parsed.schema_version == 1
