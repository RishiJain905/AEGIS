"""Publication immutability tests."""

from __future__ import annotations

from pathlib import Path

from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.publication import publish_package

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"


def test_publish_is_immutable(tmp_path: Path) -> None:
    package_dir = FIXTURES / "valid-minimal"
    output_dir = tmp_path / "published"

    published_path, diagnostics = publish_package(package_dir, output_dir)
    assert not diagnostics
    assert published_path.exists()

    _, second_diagnostics = publish_package(package_dir, output_dir)
    assert any(d.code == ScenarioErrorCode.PUBLICATION_CONFLICT for d in second_diagnostics)
