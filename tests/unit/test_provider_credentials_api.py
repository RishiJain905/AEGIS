"""The credential and catalogue routes, driven entirely by fakes.

Two things are on trial here. The first is that a plaintext API key never leaves the
server: it goes into the PUT body, into the verification call, and into the ciphertext
— and into nothing else, least of all a response. Every assertion below re-checks the
whole response body for the key rather than trusting the field list.

The second is ownership: the routes read the actor's own user id and nothing else, so
there is no request an operator can compose that reaches another operator's key.

No network and no database — the registry and the credential store are stand-ins.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_api.auth.deps import require_actor
from aegis_api.provider_credentials.router import (
    credential_write_guard,
    provider_credential_uow,
    provider_registry,
    provider_runtime_settings,
    router,
)
from aegis_contracts import (
    AegisEnvironment,
    AegisSettings,
    AuthenticatedActorV1,
    AuthMethodV1,
    PermissionV1,
    PlatformRoleV1,
)
from aegis_contracts.generation import (
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
)
from aegis_contracts.versioning import (
    AUTHENTICATED_ACTOR_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
)
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_persistence.credentials import (
    decrypt_api_key,
    derive_key_hint,
    encrypt_api_key,
    generate_encryption_key,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

_OWNER = "user:alpha"
_INTRUDER = "user:bravo"
_API_KEY = "sk-live-000000000000000000wxyz"
_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

_ALL_PROVIDERS = ("openai-compatible", "openai", "openrouter", "ollama-cloud")


class _StoredCredential:
    def __init__(
        self,
        *,
        user_id: str,
        provider: str,
        ciphertext: bytes,
        key_hint: str,
        verified_at: datetime | None,
        now: datetime,
    ) -> None:
        self.user_id = user_id
        self.provider = provider
        self.ciphertext = ciphertext
        self.key_hint = key_hint
        self.algorithm = "fernet"
        self.verified_at = verified_at
        self.created_at = now
        self.updated_at = now


class _FakeCredentialRepository:
    """The persistence contract this router depends on, in memory and self-scoped."""

    def __init__(self, encryption_key: str) -> None:
        self._encryption_key = encryption_key
        self.rows: dict[tuple[str, str], _StoredCredential] = {}

    async def get(self, user_id: str, provider: str) -> _StoredCredential | None:
        return self.rows.get((user_id, provider))

    async def list_status(self, user_id: str) -> list[_StoredCredential]:
        return [row for (owner, _), row in sorted(self.rows.items()) if owner == user_id]

    async def upsert(
        self,
        *,
        user_id: str,
        provider: str,
        ciphertext: bytes,
        key_hint: str,
        verified_at: datetime | None,
        now: datetime,
    ) -> _StoredCredential:
        row = _StoredCredential(
            user_id=user_id,
            provider=provider,
            ciphertext=ciphertext,
            key_hint=key_hint,
            verified_at=verified_at,
            now=now,
        )
        self.rows[(user_id, provider)] = row
        return row

    async def delete(self, user_id: str, provider: str) -> bool:
        return self.rows.pop((user_id, provider), None) is not None

    async def get_decrypted_api_key(
        self,
        user_id: str,
        provider: str,
        *,
        encryption_key: str,
    ) -> str | None:
        row = self.rows.get((user_id, provider))
        if row is None:
            return None
        return decrypt_api_key(row.ciphertext, key=encryption_key)

    def store(self, *, user_id: str, provider: str, api_key: str) -> None:
        self.rows[(user_id, provider)] = _StoredCredential(
            user_id=user_id,
            provider=provider,
            ciphertext=encrypt_api_key(api_key, key=self._encryption_key),
            key_hint=derive_key_hint(api_key),
            verified_at=_NOW,
            now=_NOW,
        )


class _FakeUnitOfWork:
    def __init__(self, repository: _FakeCredentialRepository) -> None:
        self.provider_credentials = repository


class _FakeListingProvider:
    """An endpoint-backed adapter: it can enumerate models, and it may refuse."""

    def __init__(
        self,
        provider_id: str,
        *,
        models: list[str] | None = None,
        error: ProviderRuntimeError | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._models = models or []
        self._error = error
        self.list_models_calls = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            provider_id=self._provider_id,
            capabilities=[ProviderCapability.CHAT],
        )

    async def generate(self, request: Any) -> Any:  # pragma: no cover - never called here
        raise NotImplementedError

    async def list_models(self) -> list[str]:
        self.list_models_calls += 1
        if self._error is not None:
            raise self._error
        return self._models


class _FakeRegistry:
    def __init__(
        self,
        *,
        provider_ids: tuple[str, ...] = _ALL_PROVIDERS,
        provider: _FakeListingProvider | None = None,
    ) -> None:
        self._provider_ids = provider_ids
        self._provider = provider
        self.api_keys_seen: list[str | None] = []

    def list_providers(self) -> list[dict[str, object]]:
        return [
            {"providerId": provider_id, "capabilities": {}}
            for provider_id in self._provider_ids
        ]

    def resolve_with_credentials(
        self,
        provider_id: str,
        *,
        api_key: str | None = None,
        model_id: str | None = None,
    ) -> _FakeListingProvider:
        if provider_id not in self._provider_ids:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message=f"Unknown provider: {provider_id}",
                )
            )
        self.api_keys_seen.append(api_key)
        return self._provider or _FakeListingProvider(provider_id)


def _actor(user_id: str) -> AuthenticatedActorV1:
    return AuthenticatedActorV1(
        schema_version=AUTHENTICATED_ACTOR_SCHEMA_VERSION,
        user_id=user_id,
        display_name=user_id,
        roles=[PlatformRoleV1.OPERATOR],
        permissions=[PermissionV1.RUNS_READ, PermissionV1.RUNS_WRITE],
        session_id="session-provider-credentials",
        auth_method=AuthMethodV1.DEV,
    )


def _settings(encryption_key: str | None) -> AegisSettings:
    return AegisSettings(
        AEGIS_ENV=AegisEnvironment.TEST,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="aegis",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="minio",
        S3_SECRET_KEY="minio123",
        S3_BUCKET="aegis",
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_ENABLED=False,
        AEGIS_WS_DEV_AUTH_ENABLED=False,
        AEGIS_OIDC_ENABLED=False,
        AEGIS_CORS_ALLOWED_ORIGINS="http://localhost:3000",
        AEGIS_CREDENTIAL_ENCRYPTION_KEY=encryption_key,
    )


def _client(
    *,
    repository: _FakeCredentialRepository,
    registry: _FakeRegistry,
    encryption_key: str | None,
    actor_user_id: str = _OWNER,
    local_model: str = "local-model",
) -> TestClient:
    app = FastAPI()
    app.state.settings = _settings(encryption_key)
    app.include_router(router)

    async def _uow() -> Any:
        yield _FakeUnitOfWork(repository)

    app.dependency_overrides[require_actor] = lambda: _actor(actor_user_id)
    app.dependency_overrides[credential_write_guard] = lambda: _actor(actor_user_id)
    app.dependency_overrides[provider_credential_uow] = _uow
    app.dependency_overrides[provider_registry] = lambda: registry
    app.dependency_overrides[provider_runtime_settings] = lambda: ProviderSettings(
        AEGIS_PROVIDER_LOCAL_MODEL=local_model
    )
    return TestClient(app)


@pytest.fixture
def encryption_key() -> str:
    return generate_encryption_key()


@pytest.fixture
def repository(encryption_key: str) -> _FakeCredentialRepository:
    return _FakeCredentialRepository(encryption_key)


def _assert_no_key_material(response_text: str) -> None:
    assert _API_KEY not in response_text
    # The hint is the only fragment allowed out; the rest of the key must be absent.
    assert _API_KEY[:-4] not in response_text


# --------------------------------------------------------------------------- connect


def test_connecting_verifies_the_key_then_stores_it_encrypted(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    registry = _FakeRegistry(provider=_FakeListingProvider("openai", models=["gpt-4o-mini"]))
    client = _client(repository=repository, registry=registry, encryption_key=encryption_key)

    response = client.put("/api/v1/provider-credentials/openai", json={"apiKey": _API_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai"
    assert body["configured"] is True
    assert body["keyHint"] == "wxyz"
    assert body["verifiedAt"] is not None
    _assert_no_key_material(response.text)

    # Verification used the real key, and the stored ciphertext decrypts back to it.
    assert registry.api_keys_seen == [_API_KEY]
    stored = repository.rows[(_OWNER, "openai")]
    assert _API_KEY.encode("utf-8") not in stored.ciphertext
    assert decrypt_api_key(stored.ciphertext, key=encryption_key) == _API_KEY


def test_a_rejected_key_is_reported_as_a_bad_request_and_never_stored(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    provider = _FakeListingProvider(
        "openrouter",
        error=ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.CREDENTIALS_MISSING,
                message="Provider 'openrouter' rejected the API key",
            )
        ),
    )
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=provider),
        encryption_key=encryption_key,
    )

    response = client.put("/api/v1/provider-credentials/openrouter", json={"apiKey": _API_KEY})

    assert response.status_code == 400
    _assert_no_key_material(response.text)
    assert repository.rows == {}


def test_an_unreachable_provider_is_a_bad_gateway_and_never_stored(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    provider = _FakeListingProvider(
        "ollama-cloud",
        error=ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="Provider 'ollama-cloud' model listing failed",
                retryable=True,
            )
        ),
    )
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=provider),
        encryption_key=encryption_key,
    )

    response = client.put("/api/v1/provider-credentials/ollama-cloud", json={"apiKey": _API_KEY})

    assert response.status_code == 502
    _assert_no_key_material(response.text)
    assert repository.rows == {}


def test_without_an_encryption_key_the_server_refuses_to_take_the_key(
    repository: _FakeCredentialRepository,
) -> None:
    registry = _FakeRegistry(provider=_FakeListingProvider("openai", models=["gpt-4o-mini"]))
    client = _client(repository=repository, registry=registry, encryption_key=None)

    response = client.put("/api/v1/provider-credentials/openai", json={"apiKey": _API_KEY})

    assert response.status_code == 503
    _assert_no_key_material(response.text)
    assert repository.rows == {}
    # It must not even have been sent to the provider for verification.
    assert registry.api_keys_seen == []


def test_a_present_but_unusable_encryption_key_refuses_the_key_just_as_firmly(
    repository: _FakeCredentialRepository,
) -> None:
    # Presence is not usability. A deployment that sets the variable to something that
    # is not a Fernet key can no more store a credential than one that left it unset,
    # and must discover that before the operator's key is sent anywhere.
    registry = _FakeRegistry(provider=_FakeListingProvider("openai", models=["gpt-4o-mini"]))
    client = _client(
        repository=repository,
        registry=registry,
        encryption_key="not-a-fernet-key",
    )

    response = client.put("/api/v1/provider-credentials/openai", json={"apiKey": _API_KEY})

    assert response.status_code == 503
    _assert_no_key_material(response.text)
    assert repository.rows == {}
    assert registry.api_keys_seen == []


def test_an_unusable_encryption_key_is_a_configuration_error_when_listing_models(
    repository: _FakeCredentialRepository,
) -> None:
    # The read path used to let this through as an unhandled 500: it caught only the
    # "ciphertext will not decrypt" error, and an unusable deployment key is a sibling
    # of that, not a subclass. Both paths answer the same way now.
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    registry = _FakeRegistry(provider=_FakeListingProvider("openai", models=["gpt-4o-mini"]))
    client = _client(
        repository=repository,
        registry=registry,
        encryption_key="not-a-fernet-key",
    )

    response = client.get("/api/v1/providers/openai/models")

    assert response.status_code == 503
    _assert_no_key_material(response.text)
    assert registry.api_keys_seen == []


def test_the_local_provider_takes_no_credential(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    response = client.put(
        "/api/v1/provider-credentials/openai-compatible", json={"apiKey": _API_KEY}
    )

    assert response.status_code == 404
    assert repository.rows == {}


def test_an_unknown_provider_is_not_found(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    response = client.put("/api/v1/provider-credentials/anthropic", json={"apiKey": _API_KEY})

    assert response.status_code == 404
    assert repository.rows == {}


def test_a_provider_the_deployment_does_not_offer_is_not_found(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    # An operator who narrows AEGIS_PROVIDER_EGRESS_ALLOWLIST removes a provider from
    # the registry entirely. That must read as "not offered here", not as a crash.
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider_ids=("openai-compatible", "openai")),
        encryption_key=encryption_key,
    )

    response = client.put("/api/v1/provider-credentials/openrouter", json={"apiKey": _API_KEY})

    assert response.status_code == 404
    assert repository.rows == {}


def test_a_blank_key_is_refused_without_echoing_the_body(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=_FakeListingProvider("openai")),
        encryption_key=encryption_key,
    )

    response = client.put("/api/v1/provider-credentials/openai", json={"apiKey": "   "})

    assert response.status_code == 400
    assert repository.rows == {}


# ---------------------------------------------------------------------------- status


def test_status_reports_every_offered_provider_without_key_material(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/provider-credentials")

    assert response.status_code == 200
    body = response.json()
    assert [entry["provider"] for entry in body] == ["openai", "openrouter", "ollama-cloud"]
    connected = next(entry for entry in body if entry["provider"] == "openai")
    assert connected["configured"] is True
    assert connected["keyHint"] == "wxyz"
    unconnected = next(entry for entry in body if entry["provider"] == "openrouter")
    assert unconnected["configured"] is False
    assert unconnected["keyHint"] is None
    _assert_no_key_material(response.text)


def test_one_operator_cannot_see_anothers_connected_providers(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
        actor_user_id=_INTRUDER,
    )

    response = client.get("/api/v1/provider-credentials")

    assert response.status_code == 200
    assert all(entry["configured"] is False for entry in response.json())
    _assert_no_key_material(response.text)


# ------------------------------------------------------------------------ disconnect


def test_disconnecting_removes_only_the_callers_credential(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    repository.store(user_id=_INTRUDER, provider="openai", api_key="sk-other-operator-key-9999")
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    response = client.delete("/api/v1/provider-credentials/openai")

    assert response.status_code == 204
    assert (_OWNER, "openai") not in repository.rows
    assert (_INTRUDER, "openai") in repository.rows


def test_disconnecting_something_never_connected_is_not_an_error(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    assert client.delete("/api/v1/provider-credentials/openai").status_code == 204


# ------------------------------------------------------------------------ model list


def test_the_local_provider_reports_its_configured_model_without_a_credential(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    registry = _FakeRegistry(provider=_FakeListingProvider("openai-compatible"))
    client = _client(
        repository=repository,
        registry=registry,
        encryption_key=encryption_key,
        local_model="qwen3-30b",
    )

    response = client.get("/api/v1/providers/openai-compatible/models")

    assert response.status_code == 200
    assert response.json()["models"] == [{"id": "qwen3-30b", "label": "qwen3-30b"}]
    # No credential was needed, so no provider call was made.
    assert registry.api_keys_seen == []


def test_a_cloud_catalogue_is_fetched_with_the_callers_own_key(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openrouter", api_key=_API_KEY)
    provider = _FakeListingProvider(
        "openrouter", models=["anthropic/claude-3", "meta-llama/llama-3"]
    )
    registry = _FakeRegistry(provider=provider)
    client = _client(
        repository=repository,
        registry=registry,
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/openrouter/models")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openrouter"
    assert [entry["id"] for entry in body["models"]] == [
        "anthropic/claude-3",
        "meta-llama/llama-3",
    ]
    # The catalogue was fetched on the caller's own subscription, decrypted for the call.
    assert registry.api_keys_seen == [_API_KEY]
    _assert_no_key_material(response.text)


def test_listing_models_without_a_stored_credential_is_a_bad_request(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=_FakeListingProvider("openai")),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/openai/models")

    assert response.status_code == 400


def test_openai_catalogue_drops_models_that_cannot_hold_a_conversation(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    provider = _FakeListingProvider(
        "openai",
        models=[
            "dall-e-3",
            "gpt-4o-mini",
            "text-embedding-3-small",
            "tts-1",
            "whisper-1",
            "omni-moderation-latest",
        ],
    )
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=provider),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/openai/models")

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()["models"]] == ["gpt-4o-mini"]


def test_a_revoked_key_surfaces_as_a_bad_request_when_listing(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    repository.store(user_id=_OWNER, provider="openai", api_key=_API_KEY)
    provider = _FakeListingProvider(
        "openai",
        error=ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.CREDENTIALS_MISSING,
                message="Provider 'openai' rejected the API key",
            )
        ),
    )
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider=provider),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/openai/models")

    assert response.status_code == 400
    _assert_no_key_material(response.text)


def test_listing_models_for_an_unknown_provider_is_not_found(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    assert client.get("/api/v1/providers/anthropic/models").status_code == 404


# -------------------------------------------------------------------- loadout picker


def test_loadout_options_name_the_four_choices_and_which_need_a_key(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/loadout-options")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "openai-compatible", "label": "Local model", "requiresCredential": False},
        {"id": "openai", "label": "OpenAI", "requiresCredential": True},
        {"id": "openrouter", "label": "OpenRouter", "requiresCredential": True},
        {"id": "ollama-cloud", "label": "Ollama Cloud", "requiresCredential": True},
    ]


def test_loadout_options_omit_a_provider_the_deployment_does_not_offer(
    repository: _FakeCredentialRepository,
    encryption_key: str,
) -> None:
    client = _client(
        repository=repository,
        registry=_FakeRegistry(provider_ids=("openai-compatible", "openai")),
        encryption_key=encryption_key,
    )

    response = client.get("/api/v1/providers/loadout-options")

    assert [option["id"] for option in response.json()] == ["openai-compatible", "openai"]


def test_the_routes_are_mounted_in_the_real_application() -> None:
    # The tests above run the router on a stand-in app, which would keep passing if it
    # were never wired into the API. Assert the real paths exist as Tasks 3 and 4
    # consume them.
    from aegis_api.main import create_app

    app = create_app(_settings("dGVzdC1rZXktbm90LWEtcmVhbC1mZXJuZXQta2V5LTE="))
    paths: set[tuple[str, str]] = set()

    def _walk(routes: Any) -> None:
        for route in routes:
            original = getattr(route, "original_router", None)
            if original is not None:
                _walk(original.routes)
                continue
            for method in getattr(route, "methods", None) or set():
                paths.add((method, getattr(route, "path", "")))

    _walk(app.routes)

    assert ("GET", "/api/v1/provider-credentials") in paths
    assert ("PUT", "/api/v1/provider-credentials/{provider}") in paths
    assert ("DELETE", "/api/v1/provider-credentials/{provider}") in paths
    assert ("GET", "/api/v1/providers/loadout-options") in paths
    assert ("GET", "/api/v1/providers/{provider}/models") in paths
