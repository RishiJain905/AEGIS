"""Contracts for picking a cloud model provider for a run.

Two obligations are pinned here. The loadout additions are *additive*: a run
launched before they existed must still parse, so the fields are optional and
the schema version does not move. And nothing in this family may ever carry key
material — the status contract exists precisely so an API response can say a
credential is connected without shipping the credential.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.entities import RulesOfEngagementV1, RunLoadoutV1
from aegis_contracts.errors import ContractValidationError
from aegis_contracts.provider_credentials import (
    LoadoutProviderOptionV1,
    ProviderCredentialStatusV1,
    ProviderModelEntryV1,
    ProviderModelListV1,
)
from aegis_contracts.versioning import (
    PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
    PROVIDER_MODEL_LIST_SCHEMA_VERSION,
    RUN_LOADOUT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)

SECRET_BEARING_NAMES = {"apikey", "key", "secret", "ciphertext", "token", "password"}


def test_a_loadout_without_provider_fields_still_parses_at_version_one() -> None:
    loadout = RunLoadoutV1.model_validate(
        {"schemaVersion": 1, "biasGuard": True, "threatTempo": True, "roe": "investigate"}
    )

    assert loadout.schema_version == RUN_LOADOUT_SCHEMA_VERSION == 1
    assert loadout.provider_id is None
    assert loadout.model_id is None


def test_a_loadout_can_pin_a_provider_and_model() -> None:
    loadout = RunLoadoutV1.model_validate(
        {
            "schemaVersion": 1,
            "roe": "observe",
            "providerId": "openrouter",
            "modelId": "anthropic/claude-sonnet-4",
        }
    )

    assert loadout.provider_id == "openrouter"
    assert loadout.model_id == "anthropic/claude-sonnet-4"
    assert loadout.roe is RulesOfEngagementV1.OBSERVE

    dumped = loadout.model_dump(by_alias=True, mode="json")
    assert dumped["providerId"] == "openrouter"
    assert dumped["modelId"] == "anthropic/claude-sonnet-4"


def test_the_loadout_still_forbids_unknown_fields() -> None:
    with pytest.raises(ValueError):
        RunLoadoutV1.model_validate({"schemaVersion": 1, "apiKey": "sk-or-secret"})


def test_credential_status_reports_connection_without_the_key() -> None:
    status = ProviderCredentialStatusV1.model_validate(
        {
            "schemaVersion": 1,
            "provider": "openrouter",
            "configured": True,
            "keyHint": "abcd",
            "verifiedAt": "2026-08-06T12:00:00Z",
        }
    )

    assert status.provider == "openrouter"
    assert status.configured is True
    assert status.key_hint == "abcd"
    assert status.verified_at == datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def test_an_unconfigured_provider_has_no_hint_and_no_verification() -> None:
    status = ProviderCredentialStatusV1.model_validate(
        {"schemaVersion": 1, "provider": "ollama-cloud", "configured": False}
    )

    assert status.key_hint is None
    assert status.verified_at is None


def test_credential_status_rejects_a_smuggled_key() -> None:
    with pytest.raises(ValueError):
        ProviderCredentialStatusV1.model_validate(
            {
                "schemaVersion": 1,
                "provider": "openrouter",
                "configured": True,
                "apiKey": "sk-or-secret",
            }
        )


@pytest.mark.parametrize(
    "model",
    [
        ProviderCredentialStatusV1,
        ProviderModelListV1,
        ProviderModelEntryV1,
        LoadoutProviderOptionV1,
    ],
)
def test_no_contract_in_this_family_declares_a_secret_bearing_field(
    model: type[ProviderCredentialStatusV1]
    | type[ProviderModelListV1]
    | type[ProviderModelEntryV1]
    | type[LoadoutProviderOptionV1],
) -> None:
    # ``keyHint`` is the deliberate exception: four plaintext characters chosen so
    # the operator can recognise which key is connected.
    names = {name.replace("_", "").lower() for name in model.model_fields}
    assert not (names & SECRET_BEARING_NAMES), names & SECRET_BEARING_NAMES


def test_a_model_list_is_a_versioned_envelope_of_id_label_pairs() -> None:
    listing = ProviderModelListV1.model_validate(
        {
            "schemaVersion": 1,
            "provider": "ollama-cloud",
            "models": [{"id": "gpt-oss:120b", "label": "gpt-oss:120b"}],
        }
    )

    assert listing.models == [ProviderModelEntryV1(id="gpt-oss:120b", label="gpt-oss:120b")]


def test_a_loadout_provider_option_declares_whether_it_needs_a_credential() -> None:
    local = LoadoutProviderOptionV1.model_validate(
        {"id": "openai-compatible", "label": "Local model", "requiresCredential": False}
    )
    cloud = LoadoutProviderOptionV1.model_validate(
        {"id": "openrouter", "label": "OpenRouter", "requiresCredential": True}
    )

    assert local.requires_credential is False
    assert cloud.requires_credential is True


def test_the_new_contracts_are_registered_in_the_version_registry() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS["provider_credential_status"] == frozenset(
        {PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION}
    )
    assert SUPPORTED_SCHEMA_VERSIONS["provider_model_list"] == frozenset(
        {PROVIDER_MODEL_LIST_SCHEMA_VERSION}
    )


def test_an_unsupported_status_version_is_rejected() -> None:
    with pytest.raises(ContractValidationError):
        ProviderCredentialStatusV1.model_validate(
            {"schemaVersion": 2, "provider": "openrouter", "configured": True}
        )
