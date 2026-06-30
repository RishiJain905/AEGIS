"""Acceptance criteria tests for Phase 08."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.publication import publish_package
from aegis_scenario_sdk.validation.pipeline import validate_package_result

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"
SILENT_RELAY = ROOT / "scenarios" / "operation-silent-relay"


def test_acceptance_valid_packages_validate_and_hash_deterministically() -> None:
    first = validate_package_result(SILENT_RELAY)
    second = validate_package_result(SILENT_RELAY)
    assert first.valid
    assert first.package_checksum == second.package_checksum


def test_acceptance_invalid_packages_fail_with_precise_diagnostics() -> None:
    result = validate_package_result(FIXTURES / "invalid-dangling-edge")
    assert not result.valid
    assert any(d.code == ScenarioErrorCode.DANGLING_REFERENCE for d in result.diagnostics)


def test_acceptance_published_versions_are_immutable(tmp_path: Path) -> None:
    output_dir = tmp_path / "published"
    _, first = publish_package(FIXTURES / "valid-minimal", output_dir)
    assert not first
    _, second = publish_package(FIXTURES / "valid-minimal", output_dir)
    assert any(d.code == ScenarioErrorCode.PUBLICATION_CONFLICT for d in second)


def test_acceptance_sdk_is_independent_of_application_internals() -> None:
    package = importlib.import_module("aegis_scenario_sdk")
    loaded = {
        module.name for module in pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    }
    forbidden = ("aegis_api", "aegis_simulation", "aegis_workers")
    for name in loaded:
        assert not any(name.startswith(prefix) for prefix in forbidden)
