"""Schema model tests for scenario manifests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"


def test_valid_minimal_fixture_parses() -> None:
    raw = yaml.safe_load((FIXTURES / "valid-minimal" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest = ScenarioManifestV1.model_validate(raw)
    assert manifest.metadata.scenario_id == "scenario:fixture-valid-minimal"
    assert len(manifest.assets) == 3


def test_extra_fields_rejected() -> None:
    raw = yaml.safe_load((FIXTURES / "valid-minimal" / "manifest.yaml").read_text(encoding="utf-8"))
    raw["unexpectedField"] = True
    with pytest.raises(ValidationError):
        ScenarioManifestV1.model_validate(raw)
