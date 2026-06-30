"""Scenario package validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.diagnostics import ValidationDiagnostic, ValidationResult
from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.loader import (
    find_manifest_path,
    load_manifest,
    load_package_manifest,
    load_raw_document,
)
from aegis_scenario_sdk.packaging.manifest import build_package_manifest, verify_package_manifest
from aegis_scenario_sdk.validation.safety import scan_raw_document
from aegis_scenario_sdk.validation.semantic import validate_semantics


@dataclass
class PackageValidation:
    valid: bool
    diagnostics: list[ValidationDiagnostic]
    manifest: ScenarioManifestV1 | None
    package_checksum: str | None


def validate_package(
    package_dir: Path,
    *,
    verify_existing_manifest: bool = True,
) -> PackageValidation:
    diagnostics: list[ValidationDiagnostic] = []
    manifest: ScenarioManifestV1 | None = None
    package_checksum: str | None = None

    try:
        manifest_path = find_manifest_path(package_dir)
        raw = load_raw_document(manifest_path)
        diagnostics.extend(scan_raw_document(raw, path=str(manifest_path)))
    except FileNotFoundError as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.PACKAGE_LAYOUT_INVALID,
                path=str(package_dir),
                message=str(exc),
            )
        )
        return PackageValidation(False, diagnostics, None, None)

    manifest, manifest_diagnostics = load_manifest(package_dir)
    diagnostics.extend(manifest_diagnostics)
    if manifest is None:
        return PackageValidation(False, diagnostics, None, None)

    diagnostics.extend(validate_semantics(manifest))

    if verify_existing_manifest:
        package_manifest, package_manifest_diagnostics = load_package_manifest(package_dir)
        diagnostics.extend(package_manifest_diagnostics)
        if package_manifest is not None:
            diagnostics.extend(verify_package_manifest(package_dir, package_manifest))
            package_checksum = package_manifest.package_checksum

    if package_checksum is None:
        package_checksum = build_package_manifest(manifest, package_dir).package_checksum

    valid = len(diagnostics) == 0
    return PackageValidation(valid, diagnostics, manifest, package_checksum)


def validate_package_result(
    package_dir: Path,
    *,
    verify_existing_manifest: bool = True,
) -> ValidationResult:
    outcome = validate_package(package_dir, verify_existing_manifest=verify_existing_manifest)
    return ValidationResult(
        valid=outcome.valid,
        diagnostics=outcome.diagnostics,
        package_checksum=outcome.package_checksum,
    )
