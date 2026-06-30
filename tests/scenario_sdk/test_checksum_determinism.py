"""Checksum determinism tests."""

from __future__ import annotations

from pathlib import Path

from aegis_scenario_sdk.packaging.manifest import build_package_manifest
from aegis_scenario_sdk.validation.pipeline import validate_package

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"


def test_same_package_produces_same_checksum() -> None:
    package_dir = FIXTURES / "valid-minimal"
    first = validate_package(package_dir, verify_existing_manifest=False)
    second = validate_package(package_dir, verify_existing_manifest=False)
    assert first.package_checksum == second.package_checksum
    assert first.package_checksum is not None
    assert first.package_checksum.startswith("sha256:")


def test_build_package_manifest_is_deterministic() -> None:
    package_dir = FIXTURES / "valid-minimal"
    outcome = validate_package(package_dir, verify_existing_manifest=False)
    assert outcome.manifest is not None
    first = build_package_manifest(outcome.manifest, package_dir)
    second = build_package_manifest(outcome.manifest, package_dir)
    assert first.package_checksum == second.package_checksum
