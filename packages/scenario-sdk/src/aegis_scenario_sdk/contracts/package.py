"""Scenario package manifest contracts."""

from __future__ import annotations

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import ScenarioId
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_scenario_sdk.version import SCENARIO_PACKAGE_MANIFEST_SCHEMA_VERSION

MANIFEST_FILENAME = "manifest.yaml"
PACKAGE_MANIFEST_FILENAME = "package.manifest.yaml"


class PackageFileEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: str = Field(min_length=1)
    checksum: str = Field(min_length=1)


class ScenarioPackageManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scenario_id: ScenarioId = Field(alias="scenarioId")
    version: str = Field(min_length=1)
    required_platform_version: str = Field(alias="requiredPlatformVersion", min_length=1)
    files: list[PackageFileEntryV1] = Field(min_length=1)
    package_checksum: str = Field(alias="packageChecksum", min_length=1)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScenarioPackageManifestV1:
        if self.schema_version != SCENARIO_PACKAGE_MANIFEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=(
                    "Unsupported scenario package manifest schema version: "
                    f"{self.schema_version}"
                ),
                details={"schemaVersion": self.schema_version},
            )
        return self
