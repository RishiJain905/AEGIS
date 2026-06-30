"""Scenario package manifest construction and verification."""

from __future__ import annotations

from pathlib import Path

from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.contracts.package import (
    MANIFEST_FILENAME,
    PACKAGE_MANIFEST_FILENAME,
    PackageFileEntryV1,
    ScenarioPackageManifestV1,
)
from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.errors import ScenarioErrorCode
from aegis_scenario_sdk.loader import list_package_files
from aegis_scenario_sdk.packaging.checksum import checksum_for_file, checksum_for_manifest_document


def build_package_manifest(
    manifest: ScenarioManifestV1,
    package_dir: Path,
) -> ScenarioPackageManifestV1:
    files: list[PackageFileEntryV1] = []
    for path in list_package_files(package_dir):
        relative = path.relative_to(package_dir).as_posix()
        if relative == MANIFEST_FILENAME or relative == "manifest.json":
            checksum = checksum_for_manifest_document(path)
        else:
            checksum = checksum_for_file(path)
        files.append(PackageFileEntryV1(path=relative, checksum=checksum))

    package_checksum = compute_package_checksum(files)
    return ScenarioPackageManifestV1(
        schema_version=1,
        scenario_id=manifest.metadata.scenario_id,
        version=manifest.metadata.version,
        required_platform_version=manifest.metadata.required_platform_version,
        files=sorted(files, key=lambda entry: entry.path),
        package_checksum=package_checksum,
    )


def compute_package_checksum(files: list[PackageFileEntryV1]) -> str:
    joined = "\n".join(
        f"{entry.path}={entry.checksum}" for entry in sorted(files, key=lambda entry: entry.path)
    )
    from aegis_scenario_sdk.packaging.checksum import checksum_for_bytes

    return checksum_for_bytes(joined.encode("utf-8"))


def write_package_manifest(package_dir: Path, package_manifest: ScenarioPackageManifestV1) -> Path:
    import yaml

    output_path = package_dir / PACKAGE_MANIFEST_FILENAME
    payload = package_manifest.model_dump(by_alias=True, mode="json")
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return output_path


def verify_package_manifest(
    package_dir: Path,
    package_manifest: ScenarioPackageManifestV1,
) -> list[ValidationDiagnostic]:
    diagnostics: list[ValidationDiagnostic] = []
    expected_entries = {entry.path: entry.checksum for entry in package_manifest.files}

    for relative_path, expected_checksum in expected_entries.items():
        file_path = package_dir / relative_path
        if not file_path.exists():
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.PACKAGE_LAYOUT_INVALID,
                    path=relative_path,
                    message="Package manifest references a missing file",
                )
            )
            continue
        if relative_path in {MANIFEST_FILENAME, "manifest.json"}:
            actual = checksum_for_manifest_document(file_path)
        else:
            actual = checksum_for_file(file_path)
        if actual != expected_checksum:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ScenarioErrorCode.CHECKSUM_MISMATCH,
                    path=relative_path,
                    message="File checksum does not match package manifest",
                    details={"expected": expected_checksum, "actual": actual},
                )
            )

    recomputed = compute_package_checksum(package_manifest.files)
    if recomputed != package_manifest.package_checksum:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.CHECKSUM_MISMATCH,
                path="packageChecksum",
                message="Package checksum does not match file entries",
                details={
                    "expected": package_manifest.package_checksum,
                    "actual": recomputed,
                },
            )
        )

    return diagnostics
