"""Validation tests for the Synthetic Training Scenario."""

from __future__ import annotations

from aegis_scenario_sdk.validation.pipeline import validate_package_result

from .helpers import SCENARIO


def test_synthetic_training_package_validates() -> None:
    result = validate_package_result(SCENARIO)
    assert result.valid, [d.message for d in result.diagnostics]
