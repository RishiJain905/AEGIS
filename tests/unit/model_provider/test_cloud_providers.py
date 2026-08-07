"""Cloud OpenAI-compatible providers: OpenRouter and Ollama Cloud.

These adapters exist so a run can be driven by the operator's *own* subscription
instead of the local llama-server. Two things make them different from the
existing hosted adapter and are pinned here:

* the API key and model id arrive per call (from a stored per-user credential
  and the run's loadout), not from the environment, so the constructor takes
  overrides that outrank the env settings;
* the loadout dialog needs the provider's live catalogue, so the adapters can
  list models;
* proving a key is a *different* request from listing the catalogue, because
  both vendors serve their catalogue to anybody who asks.

Nothing here touches the network — the SDK client is faked or its constructor
is captured.
"""

from __future__ import annotations

import logging
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
from aegis_model_provider.adapters.ollama_cloud import (
    CREDENTIAL_PROBE_MODEL_ID,
    OllamaCloudProvider,
)
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.adapters.openrouter import OpenRouterProvider
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError
from aegis_model_provider.protocol import CredentialVerifyingProvider, ModelListingProvider
from aegis_model_provider.registry import ProviderRegistry, build_provider_registry

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


def _result_or_raise(result: Any) -> Any:
    if isinstance(result, Exception):
        raise result
    return result


class _FakeClientModels:
    def __init__(self, client: _FakeCloudClient) -> None:
        self._client = client

    async def list(self) -> Any:
        self._client.model_list_calls += 1
        return _result_or_raise(self._client.transport.models_result)


class _FakeChatCompletions:
    def __init__(self, client: _FakeCloudClient) -> None:
        self._client = client

    async def create(self, **kwargs: Any) -> Any:
        self._client.completion_calls.append(kwargs)
        return _result_or_raise(self._client.transport.completion_result)


class _FakeChat:
    def __init__(self, client: _FakeCloudClient) -> None:
        self.completions = _FakeChatCompletions(client)


class _FakeCloudClient:
    """``AsyncOpenAI``'s surface, minus the network.

    Records *which* request an adapter made and how the client was built, because
    verification is only correct if it reaches an endpoint that authenticates —
    an assertion about the returned value could not tell the two apart.
    """

    def __init__(self, transport: _CloudTransport, **kwargs: Any) -> None:
        self.transport = transport
        self.kwargs = kwargs
        self.get_calls: list[str] = []
        self.completion_calls: list[dict[str, Any]] = []
        self.model_list_calls = 0
        self.closed = False
        self.chat = _FakeChat(self)
        self.models = _FakeClientModels(self)

    async def get(self, path: str, *, cast_to: Any = None, **_: Any) -> Any:
        self.get_calls.append(path)
        return _result_or_raise(self.transport.key_result)

    async def close(self) -> None:
        self.closed = True


class _CloudTransport:
    """The programmable outcome every faked client answers with."""

    def __init__(self) -> None:
        self.key_result: Any = {"data": {"label": "probe"}}
        self.completion_result: Any = None
        self.models_result: Any = _FakeModelsPage([])
        self.clients: list[_FakeCloudClient] = []

    @property
    def client(self) -> _FakeCloudClient:
        assert len(self.clients) == 1, f"expected one client, {len(self.clients)} were built"
        return self.clients[0]


@pytest.fixture()
def cloud_transport(monkeypatch: pytest.MonkeyPatch) -> _CloudTransport:
    transport = _CloudTransport()

    def _build(**kwargs: Any) -> _FakeCloudClient:
        client = _FakeCloudClient(transport, **kwargs)
        transport.clients.append(client)
        return client

    monkeypatch.setattr("openai.AsyncOpenAI", _build)
    return transport


class _Unauthorized(Exception):
    status_code = 401


class _NotFound(Exception):
    status_code = 404


class _BadRequest(Exception):
    status_code = 400


class _ServerError(Exception):
    status_code = 500


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


@pytest.mark.asyncio
async def test_list_models_treats_an_entry_without_an_id_as_a_provider_failure() -> None:
    # A page whose entries do not carry `.id` is a provider/SDK shape change, not a bug in
    # the caller — it has to arrive as a ProviderRuntimeError the router can classify,
    # never as an AttributeError escaping into a 500.
    class _Shapeless:
        pass

    page = _FakeModelsPage([])
    page.data = [_Shapeless()]  # type: ignore[list-item]
    provider = OpenRouterProvider(cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="k"))
    client = _FakeModelListingClient(page)
    provider._client = lambda: client  # type: ignore[method-assign]

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.list_models()

    assert exc.value.error.code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert client.closed is True


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


# --- credential verification ----------------------------------------------
#
# Chrome QA stored `sk-test-not-a-real-key-0000` against OpenRouter and Ollama
# Cloud and got a CONNECTED badge from both. Verification was "fetch the
# catalogue on the operator's key" — and both vendors serve `/models` to
# unauthenticated callers, so the call could not fail on a bad key. These tests
# pin the endpoint each adapter proves a key against, because the *result* of a
# verification says nothing about whether it verified anything.


def test_every_credential_backed_adapter_can_prove_a_key() -> None:
    registry = build_provider_registry(cloud_settings())

    for provider_id in ("openai", "openai-compatible", "openrouter", "ollama-cloud"):
        adapter = registry.resolve_with_credentials(provider_id)
        assert isinstance(adapter, CredentialVerifyingProvider), provider_id
    # Fixture-serving providers take no key, so the router can tell before asking.
    assert not isinstance(registry.resolve_with_credentials("mock"), CredentialVerifyingProvider)


@pytest.mark.asyncio
async def test_openai_verification_falls_back_to_the_catalogue_that_does_authenticate(
    cloud_transport: _CloudTransport,
) -> None:
    # OpenAI's `/models` refuses an unknown key, so listing it *is* a key check and
    # the base adapter keeps that as its default.
    transport = cloud_transport
    transport.models_result = _FakeModelsPage(["gpt-4o-mini"])
    provider = OpenAIHostedProvider(cloud_settings(), api_key_override="sk-operator-openai")

    await provider.verify_credentials()

    assert transport.client.model_list_calls == 1
    assert transport.client.kwargs["api_key"] == "sk-operator-openai"
    assert transport.client.closed is True


@pytest.mark.asyncio
async def test_openai_verification_reports_a_refused_key_as_credentials_missing(
    cloud_transport: _CloudTransport,
) -> None:
    cloud_transport.models_result = _Unauthorized("invalid api key")
    provider = OpenAIHostedProvider(cloud_settings(), api_key_override="sk-not-a-real-key-0000")

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING


@pytest.mark.asyncio
async def test_openrouter_verification_asks_the_key_endpoint_not_the_public_catalogue(
    cloud_transport: _CloudTransport,
) -> None:
    provider = OpenRouterProvider(cloud_settings(), api_key_override="sk-or-operator-key")

    await provider.verify_credentials()

    client = cloud_transport.client
    assert client.get_calls == ["/key"]
    assert client.model_list_calls == 0
    assert client.kwargs["api_key"] == "sk-or-operator-key"
    # The probe must stay under the allowlisted destination, not reach a new host.
    assert client.kwargs["base_url"] == OPENROUTER_BASE_URL
    assert client.closed is True


@pytest.mark.asyncio
async def test_openrouter_verification_rejects_a_key_the_endpoint_refuses(
    cloud_transport: _CloudTransport,
) -> None:
    cloud_transport.key_result = _Unauthorized("No auth credentials found")
    provider = OpenRouterProvider(cloud_settings(), api_key_override="sk-test-not-a-real-key-0000")

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING
    assert cloud_transport.client.closed is True


@pytest.mark.asyncio
async def test_openrouter_verification_reports_an_unreachable_endpoint_as_unavailable(
    cloud_transport: _CloudTransport,
) -> None:
    cloud_transport.key_result = _ServerError("bad gateway")
    provider = OpenRouterProvider(cloud_settings(), api_key_override="sk-or-operator-key")

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert exc.value.error.retryable is True


@pytest.mark.asyncio
async def test_ollama_cloud_verification_probes_with_a_model_that_cannot_exist(
    cloud_transport: _CloudTransport,
) -> None:
    # Ollama Cloud has no key-introspection endpoint, so the probe is a chat request
    # for a model nobody serves: a 404 means the request got past authentication,
    # which is the whole question. It cannot spend tokens — there is no model to run.
    cloud_transport.completion_result = _NotFound("model not found")
    provider = OllamaCloudProvider(cloud_settings(), api_key_override="ok-operator-key")

    await provider.verify_credentials()

    client = cloud_transport.client
    assert len(client.completion_calls) == 1
    probe = client.completion_calls[0]
    assert probe["model"] == CREDENTIAL_PROBE_MODEL_ID
    assert probe["max_tokens"] == 1
    assert client.model_list_calls == 0
    assert client.kwargs["api_key"] == "ok-operator-key"
    assert client.kwargs["base_url"] == OLLAMA_CLOUD_BASE_URL
    assert client.closed is True


@pytest.mark.asyncio
async def test_ollama_cloud_verification_accepts_a_model_not_found_reported_as_a_bad_request(
    cloud_transport: _CloudTransport,
) -> None:
    # Same signal, different status: the endpoint authenticated the caller and then
    # complained about the model. That is a working key.
    cloud_transport.completion_result = _BadRequest(
        f"model '{CREDENTIAL_PROBE_MODEL_ID}' not found, try pulling it first"
    )
    provider = OllamaCloudProvider(cloud_settings(), api_key_override="ok-operator-key")

    await provider.verify_credentials()

    assert cloud_transport.client.closed is True


@pytest.mark.asyncio
async def test_ollama_cloud_verification_rejects_a_key_the_endpoint_refuses(
    cloud_transport: _CloudTransport,
) -> None:
    cloud_transport.completion_result = _Unauthorized("unauthorized")
    provider = OllamaCloudProvider(cloud_settings(), api_key_override="sk-test-not-a-real-key-0000")

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING
    assert cloud_transport.client.closed is True


@pytest.mark.asyncio
async def test_ollama_cloud_verification_reports_a_timeout_as_unavailable(
    cloud_transport: _CloudTransport,
) -> None:
    # An operator whose key never got an answer has nothing to fix; that is a 502
    # upstream, not a 400 against their key.
    cloud_transport.completion_result = TimeoutError("request timed out")
    provider = OllamaCloudProvider(cloud_settings(), api_key_override="ok-operator-key")

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert exc.value.error.retryable is True


@pytest.mark.asyncio
async def test_verification_without_a_key_never_reaches_the_network(
    cloud_transport: _CloudTransport,
) -> None:
    provider = OpenRouterProvider(cloud_settings())

    with pytest.raises(ProviderRuntimeError) as exc:
        await provider.verify_credentials()

    assert exc.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING
    assert cloud_transport.clients == []


# --- registry -------------------------------------------------------------


def test_build_provider_registry_registers_both_cloud_providers() -> None:
    registry = build_provider_registry(cloud_settings())

    registered = {entry["providerId"] for entry in registry.list_providers()}

    assert {"openrouter", "ollama-cloud"} <= registered


def test_a_narrowed_allowlist_removes_the_cloud_providers_without_breaking_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # An operator who allowlists only the local endpoint has declared the cloud
    # providers off-limits; the registry must still build, and asking for one must be
    # an honest "unknown provider" rather than a dead API. Silence would be wrong
    # though — the drop has to say which provider and why.
    settings = ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="https://api.openai.com/v1,http://localhost:8086/v1",
    )

    with caplog.at_level(logging.WARNING, logger="aegis_model_provider.registry"):
        registry = build_provider_registry(settings)

    registered = {entry["providerId"] for entry in registry.list_providers()}
    assert "openai-compatible" in registered
    assert not ({"openrouter", "ollama-cloud"} & registered)
    warnings = "\n".join(record.getMessage() for record in caplog.records)
    assert "openrouter" in warnings
    assert "ollama-cloud" in warnings
    assert "AEGIS_PROVIDER_EGRESS_ALLOWLIST" in warnings
    with pytest.raises(ProviderRuntimeError) as exc:
        registry.resolve_with_credentials("openrouter", api_key="k")
    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


def test_de_allowlisting_the_default_provider_fails_the_build_instead_of_the_run() -> None:
    # Dropping the provider the whole deployment runs on would boot a clean API whose
    # every generation then dies with "Unknown provider" and no hint at the allowlist.
    # That misconfiguration belongs at startup.
    settings = ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_DEFAULT=ProviderKind.OPENROUTER,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="http://localhost:8086/v1",
    )

    with pytest.raises(ProviderRuntimeError) as exc:
        build_provider_registry(settings)

    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED


def test_a_malformed_cloud_base_url_is_not_mistaken_for_a_deliberate_exclusion() -> None:
    # A typo in AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL raises the same VALIDATION_FAILED
    # as an off-allowlist destination, but it is a broken config, not a policy choice.
    settings = ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL="ollama.com/v1",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST=ALL_BASE_URLS,
    )

    with pytest.raises(ProviderRuntimeError) as exc:
        build_provider_registry(settings)

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


def test_a_settings_less_registry_refuses_to_swallow_a_callers_key() -> None:
    # Binding a key needs the settings the fresh adapter is built from. Without them the
    # only thing the registry could hand back is the shared env-configured adapter — which
    # would run the caller's request on the deployment's own credential and say nothing.
    # A registry built without settings is a test/harness construction, so this is latent;
    # it stays latent by failing loudly the moment a real caller reaches it.
    registry = ProviderRegistry(
        {"openrouter": OpenRouterProvider(cloud_settings(AEGIS_PROVIDER_OPENROUTER_API_KEY="env"))},
        default_provider_id="openrouter",
    )

    with pytest.raises(ProviderRuntimeError) as exc:
        registry.resolve_with_credentials("openrouter", api_key="per-user-key")

    assert exc.value.error.code == ProviderErrorCode.VALIDATION_FAILED

    # Asking without a key is still the shared instance: nothing to bind, nothing to hide.
    assert registry.resolve_with_credentials("openrouter").provider_id == "openrouter"


def test_resolve_with_credentials_accepts_no_key_for_the_local_provider(
    captured_clients: _CapturedClients,
) -> None:
    settings = cloud_settings(AEGIS_PROVIDER_LOCAL_API_KEY="llama-cpp")
    registry = build_provider_registry(settings)

    provider = registry.resolve_with_credentials("openai-compatible", api_key=None)

    assert provider.provider_id == "openai-compatible"
    provider._client()  # type: ignore[attr-defined]
    assert captured_clients[0]["api_key"] == "llama-cpp"
