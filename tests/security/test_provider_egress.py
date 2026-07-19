"""Provider destination allowlist bypass attempts."""

from __future__ import annotations

import pytest
from aegis_contracts.generation import ProviderErrorCode
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError


def test_hosted_adapter_rejects_metadata_service_destination() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_OPENAI_BASE_URL="http://169.254.169.254/latest",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1",
    )
    with pytest.raises(ProviderRuntimeError) as exc:
        OpenAIHostedProvider(settings)
    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


def test_host_suffix_trick_cannot_bypass_exact_allowlist() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_OPENAI_BASE_URL="https://api.openai.com.evil.example/v1",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1",
    )
    with pytest.raises(ProviderRuntimeError):
        OpenAIHostedProvider(settings)


def test_credentials_embedded_in_allowed_url_fail_closed() -> None:
    destination = "https://user:password@api.openai.com/v1"
    settings = ProviderSettings(
        AEGIS_PROVIDER_OPENAI_BASE_URL=destination,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST=destination,
    )
    with pytest.raises(ProviderRuntimeError):
        OpenAIHostedProvider(settings)


def test_trailing_slash_normalization_preserves_exact_allowed_destination() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_OPENAI_BASE_URL="https://api.openai.com/v1/",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1",
    )
    provider = OpenAIHostedProvider(settings)
    assert provider.provider_id == "openai"


def test_openai_compatible_adapter_enforces_local_destination_allowlist() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_LOCAL_BASE_URL="http://127.0.0.1:8080/v1",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="http://localhost:8080/v1",
    )
    with pytest.raises(ProviderRuntimeError):
        OpenAICompatibleProvider(settings)


def test_empty_local_destination_does_not_fall_back_to_hosted_provider() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_LOCAL_BASE_URL="",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1",
    )
    with pytest.raises(ProviderRuntimeError):
        OpenAICompatibleProvider(settings)


def test_llama_server_local_endpoint_is_allowlisted() -> None:
    settings = ProviderSettings(
        AEGIS_PROVIDER_LOCAL_BASE_URL="http://localhost:8080/v1",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="http://localhost:8080/v1",
    )
    provider = OpenAICompatibleProvider(settings)
    assert provider.provider_id == "openai-compatible"


def test_default_settings_target_llama_server_and_build_registry() -> None:
    # The default egress allowlist must cover both provider base URLs, since
    # build_provider_registry constructs the hosted and compatible adapters and
    # each enforces the allowlist in its constructor.
    from aegis_model_provider import build_provider_registry

    settings = ProviderSettings(_env_file=None)
    assert settings.AEGIS_PROVIDER_LOCAL_BASE_URL == "http://localhost:8080/v1"
    assert "http://localhost:8080/v1" in settings.provider_egress_allowlist
    build_provider_registry(settings)
