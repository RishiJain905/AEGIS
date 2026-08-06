"""Cloud model-provider credentials and catalogue contracts.

A run can be driven by the operator's own model subscription (OpenAI, OpenRouter,
Ollama Cloud) instead of the local endpoint. The API key is stored encrypted per user
account; these contracts are what the console is allowed to see about it.

Nothing here carries key material, and nothing here should ever be made to. The single
plaintext fragment is ``keyHint`` — the last four characters — which exists so an
operator can tell *which* key is connected without the server disclosing it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import UtcTimestamp
from aegis_contracts.versioning import (
    PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
    PROVIDER_MODEL_LIST_SCHEMA_VERSION,
    assert_supported_schema_version,
)

__all__ = [
    "LoadoutProviderOptionV1",
    "ProviderCredentialStatusV1",
    "ProviderModelEntryV1",
    "ProviderModelListV1",
]


class ProviderCredentialStatusV1(BaseModel):
    """Whether a user has a usable key for one provider — never the key itself."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    provider: str = Field(min_length=1, max_length=64)
    configured: bool
    # Last four characters of the stored key, so the UI can say "Connected (…abcd)".
    key_hint: str | None = Field(default=None, alias="keyHint", max_length=8)
    verified_at: UtcTimestamp | None = Field(default=None, alias="verifiedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ProviderCredentialStatusV1:
        assert_supported_schema_version("provider_credential_status", self.schema_version)
        if self.schema_version != PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported provider credential status schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ProviderModelEntryV1(BaseModel):
    """One selectable model. ``label`` is what the picker shows; ``id`` is what is sent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)


class ProviderModelListV1(BaseModel):
    """A provider's live catalogue for the account that asked."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    provider: str = Field(min_length=1, max_length=64)
    models: list[ProviderModelEntryV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ProviderModelListV1:
        assert_supported_schema_version("provider_model_list", self.schema_version)
        if self.schema_version != PROVIDER_MODEL_LIST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported provider model list schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class LoadoutProviderOptionV1(BaseModel):
    """One provider the launch dialog may offer.

    ``requires_credential`` is what tells the dialog whether to demand a key before the
    run can launch; the local endpoint needs none. Fixture-serving providers (mock,
    recorded) are env-only and never appear in this list.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    requires_credential: bool = Field(alias="requiresCredential")
