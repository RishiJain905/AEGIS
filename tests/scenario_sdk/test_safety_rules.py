"""Safety rule tests."""

from __future__ import annotations

from pathlib import Path

from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.validation.pipeline import validate_package_result

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"


def test_unsafe_url_in_rubric_rejected() -> None:
    result = validate_package_result(FIXTURES / "invalid-unsafe-content")
    assert not result.valid
    assert any(d.code == ScenarioErrorCode.UNSAFE_CONTENT for d in result.diagnostics)
