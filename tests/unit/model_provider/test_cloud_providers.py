"""Cloud OpenAI-compatible providers: OpenRouter and Ollama Cloud.

These adapters exist so a run can be driven by the operator's *own* subscription
instead of the local llama-server. Two things make them different from the
existing hosted adapter and are pinned here:

* the API key and model id arrive per call (from a stored per-user credential
  and the run's loadout), not from the environment, so the constructor takes
  overrides that outrank the env settings;
* the loadout dialog needs the provider's live catalogue, so the adapters can
  list models.

Nothing here touches the network — the SDK client is faked or its constructor
is captured.
"""

from __future__ import annotations

from typing import Any

import pytest
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderErrorCode,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
)
from aegis_model_provider.adapters.ollama_cloud import OllamaCloudProvider
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openrouter import OpenRouterProvider
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError
from aegis_model_provider.protocol import ModelListingProvider
from aegis_model_provider.registry import build_provider_registry

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
ALL_BASE_URLS = ",".join(
    [
        "https://api.openai.com/v1",
        "http://localhost:8086/v1",
        OPENROUTER_BASE_URL,
        OLLAMA_CLOUD_BASE_URL,
    ]
)


def cloud_settings(**overrides: Any) -> ProviderSettings:
    return ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST=ALL_BASE_URLS,
        **overrides,
    )


def request_for(provider_id: str, *, model_id: str | None = None) -> GenerationRequestV1:
    """A request as the agent runtime builds it — a synthetic ``<provider>-v1`` model id."""
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id=provider_id,
            model_id=model_id if model_id is not None else f"{provider_id}-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Triage the run"),
        ],
    )


class _CapturedClients(list[dict[str, Any]]):
    """The keyword arguments every ``AsyncOpenAI`` construction was given."""


@pytest.fixture()
def captured_clients(monkeypatch: pytest.MonkeyPatch) -> _CapturedClients:
    captured = _CapturedClients()

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)
    return captured


class _FakeModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id


class _FakeModelsPage:
    def __init__(self, ids: list[str]) -> None:
        self.data = [_FakeModel(model_id) for model_id in ids]


class _FakeModels:
    def __init__(self, result: Any) -> None:
        self._result = result

    async def list(self) -> Any:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeModelListingClient:
    def __init__(self, result: Any) -> None:
        self.models = _FakeModels(result)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


# --- identity -------------------------------------------------------------


def test_openrouter_provider_id_is_wire_stable() -> None:
    provider = OpenRouterProvider(cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="sk-or-test"))

    assert provider.provider_id == "openrouter"
    assert ProviderKind.OPENROUTER.value == "openrouter"


def test_ollama_cloud_provider_id_is_wire_stable() -> None:
    provider = OllamaCloudProvider(cloud_settings(AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY="ok-test"))

    assert provider.provider_id == "ollama-cloud"
    assert ProviderKind.OLLAMA_CLOUD.value == "ollama-cloud"


def test_default_egress_allowlist_covers_both_cloud_providers() -> None:
    settings = ProviderSettings(_env_file=None)

    assert settings.AEGIS_PROVIDER_OPENROUTER_BASE_URL == OPENROUTER_BASE_URL
    assert settings.AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL == OLLAMA_CLOUD_BASE_URL
    assert OPENROUTER_BASE_URL in settings.provider_egress_allowlist
    assert OLLAMA_CLOUD_BASE_URL in settings.provider_egress_allowlist


# --- credential overrides -------------------------------------------------


def test_api_key_override_reaches_the_sdk_client(captured_clients: _CapturedClients) -> None:
    provider = OpenRouterProvider(
        cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="env-key"),
        api_key_override="per-user-key",
    )

    provider._client()

    assert captured_clients[0]["api_key"] == "per-user-key"
    assert captured_clients[0]["base_url"] == OPENROUTER_BASE_URL


def test_env_key_is_used_when_no_override_is_given(captured_clients: _CapturedClients) -> None:
    provider = OllamaCloudProvider(cloud_settings(AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY="env-key"))

    provider._client()

    assert captured_clients[0]["api_key"] == "env-key"
    assert captured_clients[0]["base_url"] == OLLAMA_CLOUD_BASE_URL


def test_missing_key_fails_as_credentials_missing() -> None:
    provider = OpenRouterProvider(cloud_settings())

    with pytest.raises(ProviderRuntimeError) as exc:
        provider._client()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING


def test_model_id_override_beats_the_env_model() -> None:
    provider = OpenRouterProvider(
        cloud_settings(
            AEGIS_PROVIDER_OPENROUTER_API_KEY="k",
            AEGIS_PROVIDER_OPENROUTER_MODEL="env/model",
        ),
        model_id_override="anthropic/claude-sonnet-4",
    )

    assert provider._resolve_model_id(request_for("openrouter")) == "anthropic/claude-sonnet-4"


def test_env_model_is_used_when_the_request_carries_only_a_synthetic_id() -> None:
    provider = OpenRouterProvider(
        cloud_settings(
            AEGIS_PROVIDER_OPENROUTER_API_KEY="k",
            AEGIS_PROVIDER_OPENROUTER_MODEL="env/model",
        )
    )

    assert provider._resolve_model_id(request_for("openrouter")) == "env/model"


def test_a_real_requested_model_wins_over_every_default() -> None:
    provider = OpenRouterProvider(
        cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="k"),
        model_id_override="override/model",
    )

    resolved = provider._resolve_model_id(request_for("openrouter", model_id="pinned/model"))

    assert resolved == "pinned/model"


def test_no_model_anywhere_fails_validation_rather_than_sending_an_empty_model() -> None:
    provider = OllamaCloudProvider(cloud_settings(AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY="k"))

    with pytest.raises(ProviderRuntimeError) as exc:
        provider._resolve_model_id(request_for("ollama-cloud"))

    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


# --- model listing --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models_normalizes_the_sdk_response() -> None:
    provider = OpenRouterProvider(cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="k"))
    client = _FakeModelListingClient(
        _FakeModelsPage(["z/model", "a/model", "z/model", "  ", "m/model"])
    )
    provider._client = lambda: client  # type: ignore[method-assign]

    models = await provider.list_models()

    assert models == ["a/model", "m/model", "z/model"]
    assert client.closed is True


@pytest.mark.asyncio
async def test_list_models_classifies_a_rejected_key_as_credentials_missing() -> None:
    class _Unauthorized(Exception):
        status_code = 401

    provider = OllamaCloudProvider(cloud_settings(AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY="bad"))
    provider._client = lambda: _FakeModelListingClient(_Unauthorized("no"))  # type: ignore[method-assign]

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.list_models()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING


@pytest.mark.asyncio
async def test_list_models_reports_an_unreachable_endpoint_as_unavailable() -> None:
    provider = OpenRouterProvider(cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="k"))
    provider._client = lambda: _FakeModelListingClient(RuntimeError("connection refused"))  # type: ignore[method-assign]

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.list_models()

    assert exc.value.error.code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert exc.value.error.retryable is True


def test_only_endpoint_backed_adapters_claim_to_list_models() -> None:
    registry = build_provider_registry(cloud_settings())

    assert isinstance(registry.resolve_with_credentials("openrouter"), ModelListingProvider)
    assert isinstance(registry.resolve_with_credentials("ollama-cloud"), ModelListingProvider)
    assert isinstance(registry.resolve_with_credentials("openai-compatible"), ModelListingProvider)
    # Fixture-serving providers have no catalogue, so a caller can tell before asking.
    assert not isinstance(registry.resolve_with_credentials("mock"), ModelListingProvider)
    assert not isinstance(registry.resolve_with_credentials("recorded"), ModelListingProvider)


@pytest.mark.asyncio
async def test_the_local_adapter_inherits_model_listing() -> None:
    provider = OpenAICompatibleProvider(cloud_settings())
    provider._client = lambda: _FakeModelListingClient(_FakeModelsPage(["local-model"]))  # type: ignore[method-assign]

    assert await provider.list_models() == ["local-model"]


# --- registry -------------------------------------------------------------


def test_build_provider_registry_registers_both_cloud_providers() -> None:
    registry = build_provider_registry(cloud_settings())

    registered = {entry["providerId"] for entry in registry.list_providers()}

    assert {"openrouter", "ollama-cloud"} <= registered


def test_a_narrowed_allowlist_removes_the_cloud_providers_without_breaking_boot() -> None:
    # An operator who allowlists only the local endpoint has declared the cloud
    # providers off-limits; the registry must still build, and asking for one must be
    # an honest "unknown provider" rather than a dead API.
    settings = ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1,http://localhost:8086/v1",
    )

    registry = build_provider_registry(settings)

    registered = {entry["providerId"] for entry in registry.list_providers()}
    assert "openai-compatible" in registered
    assert not ({"openrouter", "ollama-cloud"} & registered)
    with pytest.raises(ProviderRuntimeError) as exc:
        registry.resolve_with_credentials("openrouter", api_key="k")
    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


def test_resolve_with_credentials_builds_a_fresh_adapter_with_the_overrides(
    captured_clients: _CapturedClients,
) -> None:
    settings = cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="env-key")
    registry = build_provider_registry(settings)
    shared = registry.resolve(request_for("openrouter"))

    provider = registry.resolve_with_credentials(
        "openrouter", api_key="per-user-key", model_id="anthropic/claude-sonnet-4"
    )

    assert provider is not shared
    assert provider.provider_id == "openrouter"
    assert provider._resolve_model_id(request_for("openrouter")) == "anthropic/claude-sonnet-4"  # type: ignore[attr-defined]
    provider._client()  # type: ignore[attr-defined]
    assert captured_clients[0]["api_key"] == "per-user-key"


def test_resolve_with_credentials_rejects_an_unknown_provider() -> None:
    registry = build_provider_registry(cloud_settings())

    with pytest.raises(ProviderRuntimeError) as exc:
        registry.resolve_with_credentials("not-a-provider", api_key="k")

    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


def test_resolve_with_credentials_accepts_no_key_for_the_local_provider(
    captured_clients: _CapturedClients,
) -> None:
    settings = cloud_settings(AEGIS_PROVIDER_LOCAL_API_KEY="llama-cpp")
    registry = build_provider_registry(settings)

    provider = registry.resolve_with_credentials("openai-compatible", api_key=None)

    assert provider.provider_id == "openai-compatible"
    provider._client()  # type: ignore[attr-defined]
    assert captured_clients[0]["api_key"] == "llama-cpp"
