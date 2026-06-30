"""Scenario package loading utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from aegis_contracts.errors import ContractValidationError
from pydantic import ValidationError

from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.contracts.package import (
    MANIFEST_FILENAME,
    PACKAGE_MANIFEST_FILENAME,
    ScenarioPackageManifestV1,
)
from aegis_scenario_sdk.diagnostics import ValidationDiagnostic
from aegis_scenario_sdk.errors import ScenarioErrorCode


def load_raw_document(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    if path.suffix.lower() == ".json":
        return json.loads(text)
    raise ValueError(f"Unsupported document format: {path}")


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def find_manifest_path(package_dir: Path) -> Path:
    yaml_path = package_dir / MANIFEST_FILENAME
    if yaml_path.exists():
        return yaml_path
    json_path = package_dir / "manifest.json"
    if json_path.exists():
        return json_path
    raise FileNotFoundError(f"Missing manifest in {package_dir}")


def find_package_manifest_path(package_dir: Path) -> Path | None:
    yaml_path = package_dir / PACKAGE_MANIFEST_FILENAME
    if yaml_path.exists():
        return yaml_path
    json_path = package_dir / "package.manifest.json"
    if json_path.exists():
        return json_path
    return None


def load_manifest(
    package_dir: Path,
) -> tuple[ScenarioManifestV1 | None, list[ValidationDiagnostic]]:
    diagnostics: list[ValidationDiagnostic] = []
    try:
        manifest_path = find_manifest_path(package_dir)
    except FileNotFoundError as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.PACKAGE_LAYOUT_INVALID,
                path=str(package_dir),
                message=str(exc),
            )
        )
        return None, diagnostics

    try:
        raw = load_raw_document(manifest_path)
        manifest = ScenarioManifestV1.model_validate(raw)
        return manifest, diagnostics
    except (ValidationError, ContractValidationError) as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.SCHEMA_VALIDATION_FAILED,
                path=str(manifest_path),
                message=str(exc),
            )
        )
        return None, diagnostics


def load_package_manifest(
    package_dir: Path,
) -> tuple[ScenarioPackageManifestV1 | None, list[ValidationDiagnostic]]:
    diagnostics: list[ValidationDiagnostic] = []
    package_manifest_path = find_package_manifest_path(package_dir)
    if package_manifest_path is None:
        return None, diagnostics

    try:
        raw = load_raw_document(package_manifest_path)
        package_manifest = ScenarioPackageManifestV1.model_validate(raw)
        return package_manifest, diagnostics
    except (ValidationError, ContractValidationError) as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code=ScenarioErrorCode.SCHEMA_VALIDATION_FAILED,
                path=str(package_manifest_path),
                message=str(exc),
            )
        )
        return None, diagnostics


def list_package_files(package_dir: Path) -> list[Path]:
    ignored = {PACKAGE_MANIFEST_FILENAME, "package.manifest.json"}
    files: list[Path] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in ignored:
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return files
