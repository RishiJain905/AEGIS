"""Validation tests for Operation Silent Relay."""

from __future__ import annotations

from aegis_scenario_sdk.validation.pipeline import validate_package_result

from .helpers import SCENARIO


def test_silent_relay_package_validates() -> None:
    result = validate_package_result(SCENARIO)
    assert result.valid, [d.message for d in result.diagnostics]
