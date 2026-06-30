"""CLI tests."""

from __future__ import annotations

from pathlib import Path

from aegis_scenario_sdk.cli import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"
SILENT_RELAY = ROOT / "scenarios" / "operation-silent-relay"


def test_cli_validate_success() -> None:
    exit_code = main(["validate", str(FIXTURES / "valid-minimal")])
    assert exit_code == 0


def test_cli_validate_failure() -> None:
    exit_code = main(["validate", str(FIXTURES / "invalid-dangling-edge")])
    assert exit_code == 1


def test_cli_hash_success() -> None:
    exit_code = main(["hash", str(SILENT_RELAY)])
    assert exit_code == 0


def test_cli_package_writes_manifest() -> None:
    package_manifest = FIXTURES / "valid-minimal" / "package.manifest.yaml"
    if package_manifest.exists():
        package_manifest.unlink()
    exit_code = main(["package", str(FIXTURES / "valid-minimal")])
    assert exit_code == 0
    assert package_manifest.exists()
    package_manifest.unlink()
