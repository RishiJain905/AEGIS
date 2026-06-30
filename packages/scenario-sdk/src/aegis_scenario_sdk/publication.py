"""Immutable scenario publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.packaging.manifest import build_package_manifest, write_package_manifest
from aegis_scenario_sdk.validation.pipeline import validate_package


def publish_package(package_dir: Path, output_dir: Path) -> tuple[Path, list[ValidationDiagnostic]]:
    outcome = validate_package(package_dir, verify_existing_manifest=False)
    if not outcome.valid or outcome.diagnostics:
        return output_dir, outcome.diagnostics

    manifest = outcome.manifest
    if manifest is None:
        return output_dir, [
            ValidationDiagnostic(
                code=ScenarioErrorCode.VALIDATION_FAILED,
                path=str(package_dir),
                message="Validated package is missing a manifest",
            )
        ]

    package_manifest = build_package_manifest(manifest, package_dir)
    write_package_manifest(package_dir, package_manifest)

    scenario_slug = manifest.metadata.scenario_id.replace(":", "_")
    version_dir = output_dir / scenario_slug / manifest.metadata.version
    if version_dir.exists():
        return version_dir, [
            ValidationDiagnostic(
                code=ScenarioErrorCode.PUBLICATION_CONFLICT,
                path=str(version_dir),
                message="Published scenario version already exists and is immutable",
                details={
                    "scenarioId": manifest.metadata.scenario_id,
                    "version": manifest.metadata.version,
                },
            )
        ]

    version_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package_dir, version_dir)
    return version_dir, []
