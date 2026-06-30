"""Semantic validation failure-path tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.validation.pipeline import validate_package_result

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("invalid-duplicate-ids", ScenarioErrorCode.DUPLICATE_ID),
        ("invalid-dangling-edge", ScenarioErrorCode.DANGLING_REFERENCE),
        ("invalid-unknown-plugin", ScenarioErrorCode.UNKNOWN_PLUGIN),
        ("invalid-unsafe-content", ScenarioErrorCode.UNSAFE_CONTENT),
        ("invalid-platform-version", ScenarioErrorCode.PLATFORM_VERSION_INCOMPATIBLE),
    ],
)
def test_invalid_fixtures_fail_with_expected_code(
    fixture_name: str,
    expected_code: ScenarioErrorCode,
) -> None:
    result = validate_package_result(FIXTURES / fixture_name)
    assert not result.valid
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert expected_code in codes
