"""AEGIS Scenario SDK — declarative scenario authoring, validation, and publication."""

from aegis_scenario_sdk.cli import main
from aegis_scenario_sdk.contracts import ScenarioManifestV1, ScenarioPackageManifestV1
from aegis_scenario_sdk.diagnostics import ValidationDiagnostic, ValidationResult
from aegis_scenario_sdk.validation.pipeline import validate_package, validate_package_result
from aegis_scenario_sdk.version import SDK_VERSION

__all__ = [
    "SDK_VERSION",
    "ScenarioManifestV1",
    "ScenarioPackageManifestV1",
    "ValidationDiagnostic",
    "ValidationResult",
    "main",
    "validate_package",
    "validate_package_result",
]
