"""Cloud model-provider credentials, and the model catalogue they unlock.

An operator can point a run at their own model subscription instead of the local
endpoint. These routes are how they connect one: the key arrives once, is verified live
against the provider, and is stored encrypted against their account.

Three rules shape everything below.

*The key is theirs.* Plaintext exists in the PUT body, in the verification call, and in
the ciphertext — nowhere else. No response, error detail, or log line carries it, and
the only fragment that survives is the four-character hint the console displays.

*Every route is self-scoped.* Each handler reads ``actor.user_id`` and passes it to the
repository. There is no user parameter to tamper with, so no request an operator can
compose reaches another operator's credential.

*A provider the deployment does not offer is not an error.* Narrowing
``AEGIS_PROVIDER_EGRESS_ALLOWLIST`` removes a provider from the registry; that reads as
"not found here", never as a crash.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from aegis_contracts import AegisSettings, AuthenticatedActorV1, PermissionV1
from aegis_contracts.generation import ProviderErrorCode
from aegis_contracts.provider_credentials import (
    LoadoutProviderOptionV1,
    ProviderCredentialStatusV1,
    ProviderModelEntryV1,
    ProviderModelListV1,
)
from aegis_contracts.versioning import (
    PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
    PROVIDER_MODEL_LIST_SCHEMA_VERSION,
)
from aegis_model_provider import load_provider_settings
from aegis_model_provider.config import CLOUD_PROVIDER_KINDS, ProviderKind, ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError
from aegis_model_provider.protocol import CredentialVerifyingProvider, ModelListingProvider
from aegis_model_provider.registry import ProviderRegistry, build_provider_registry
from aegis_persistence.credentials import (
    CredentialCryptoError,
    CredentialDecryptError,
    assert_encryption_key_usable,
    derive_key_hint,
    encrypt_api_key,
)
from aegis_persistence.orm.tables import AuthUserProviderCredentialRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from aegis_api.auth.deps import require_actor, require_permission
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["provider-credentials"])

#: Connecting and disconnecting a provider is only meaningful for an operator who can
#: launch runs, so these mutations ride the same permission run creation does. A
#: read-only viewer can neither store a key nor spend one.
credential_write_guard = require_permission(PermissionV1.RUNS_WRITE)

#: The providers the launch dialog may offer, in the order it shows them. The local
#: endpoint leads because it is the default and needs nothing; the rest run on the
#: operator's own subscription. Fixture-serving providers (mock, recorded) are env-only
#: and deliberately absent.
LOADOUT_PROVIDER_OPTIONS: tuple[tuple[ProviderKind, str], ...] = (
    (ProviderKind.OPENAI_COMPATIBLE, "Local model"),
    (ProviderKind.OPENAI, "OpenAI"),
    (ProviderKind.OPENROUTER, "OpenRouter"),
    (ProviderKind.OLLAMA_CLOUD, "Ollama Cloud"),
)

#: OpenAI's catalogue is one list for every modality it sells. A model picker for a
#: chat agent should not offer embeddings, speech, or image endpoints — they would fail
#: at generation time with an opaque provider error. Matched against the model id.
_NON_CHAT_MODEL_MARKERS: tuple[str, ...] = (
    "embedding",
    "moderation",
    "tts",
    "whisper",
    "audio",
    "dall-e",
    "image",
    "realtime",
    "transcribe",
)


class ProviderCredentialConnectRequest(BaseModel):
    """The one place a plaintext provider key is allowed to appear.

    Deliberately carries no length or pattern constraints: FastAPI's default validation
    error echoes the offending input back to the caller, so a constraint here would be
    a way to make the server repeat the key. Emptiness is checked in the handler, where
    the complaint can be written without the value.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_key: str = Field(alias="apiKey")


async def provider_credential_uow() -> AsyncIterator[PostgresUnitOfWork]:
    """A unit of work for one credential request; commits when the handler returns."""
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        yield uow


def provider_runtime_settings() -> ProviderSettings:
    return load_provider_settings()


def provider_registry(
    settings: Annotated[ProviderSettings, Depends(provider_runtime_settings)],
) -> ProviderRegistry:
    return build_provider_registry(settings)


def _encryption_key(request: Request) -> str:
    """The deployment's encryption key, proven usable, or a 503 for every route alike.

    Usability is checked here rather than at each use because presence and usability are
    different questions and only the first is obvious. A key that is set but is not a
    Fernet key must fail the same way an unset one does — before a route decrypts
    anything, and before it sends an operator's API key upstream to be verified.
    """
    settings: AegisSettings = request.app.state.settings
    key = settings.AEGIS_CREDENTIAL_ENCRYPTION_KEY
    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "This deployment is not configured for cloud model providers: "
                "AEGIS_CREDENTIAL_ENCRYPTION_KEY is unset."
            ),
        )
    try:
        assert_encryption_key_usable(key)
    except CredentialCryptoError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "This deployment is not configured for cloud model providers: "
                "AEGIS_CREDENTIAL_ENCRYPTION_KEY is not a usable encryption key."
            ),
        ) from exc
    return key


def _offered_provider_ids(registry: ProviderRegistry) -> set[str]:
    return {str(entry["providerId"]) for entry in registry.list_providers()}


def _require_cloud_provider(provider: str, registry: ProviderRegistry) -> str:
    """The provider id, or 404 if it is not a cloud provider this deployment offers."""
    cloud_ids = {kind.value for kind in CLOUD_PROVIDER_KINDS}
    if provider not in cloud_ids or provider not in _offered_provider_ids(registry):
        raise HTTPException(
            status_code=404,
            detail=f"No credential-backed model provider named '{provider}' is available",
        )
    return provider


def _provider_http_error(exc: ProviderRuntimeError) -> HTTPException:
    """A provider failure the operator can act on.

    A rejected key is the operator's to fix, so it is a 400 carrying the provider's own
    classification. Anything else — timeouts, outages, malformed responses — is the
    provider being unreachable, which is a 502: the request was fine, the upstream was
    not. The message comes from the classified error, which is already redacted.
    """
    if exc.error.code == ProviderErrorCode.CREDENTIALS_MISSING:
        return HTTPException(status_code=400, detail=exc.error.message)
    return HTTPException(status_code=502, detail=exc.error.message)


async def _verify_api_key(registry: ProviderRegistry, provider: str, *, api_key: str) -> None:
    """Prove the key against the provider, or raise the failure the operator must fix.

    Deliberately *not* "fetch the catalogue and see whether it worked". OpenRouter and
    Ollama Cloud serve their model lists to unauthenticated callers, so that check
    passed for any non-empty string and stored it as verified — the defect Chrome QA
    found on 2026-08-06. Each adapter now names the endpoint that actually
    authenticates it; listing stays the model picker's errand alone.
    """
    try:
        adapter = registry.resolve_with_credentials(provider, api_key=api_key)
    except ProviderRuntimeError as exc:
        raise _provider_http_error(exc) from exc
    if not isinstance(adapter, CredentialVerifyingProvider):
        # Fixture-serving adapters have no endpoint to ask. Nothing routed here should
        # be one, so refuse the key rather than store one nothing ever checked.
        raise HTTPException(
            status_code=502,
            detail=f"Provider '{provider}' cannot verify an API key",
        )
    try:
        await adapter.verify_credentials()
    except ProviderRuntimeError as exc:
        raise _provider_http_error(exc) from exc


async def _fetch_model_ids(registry: ProviderRegistry, provider: str, *, api_key: str) -> list[str]:
    """The provider's live catalogue, fetched on this caller's key."""
    try:
        adapter = registry.resolve_with_credentials(provider, api_key=api_key)
    except ProviderRuntimeError as exc:
        raise _provider_http_error(exc) from exc
    if not isinstance(adapter, ModelListingProvider):
        # Fixture-serving adapters have no catalogue to report. Nothing routed here
        # should be one, so say the provider cannot answer rather than inventing a list.
        raise HTTPException(
            status_code=502,
            detail=f"Provider '{provider}' cannot report a model catalogue",
        )
    try:
        return await adapter.list_models()
    except ProviderRuntimeError as exc:
        raise _provider_http_error(exc) from exc


def _selectable_models(provider: str, model_ids: list[str]) -> list[ProviderModelEntryV1]:
    if provider == ProviderKind.OPENAI.value:
        model_ids = [
            model_id
            for model_id in model_ids
            if not any(marker in model_id.lower() for marker in _NON_CHAT_MODEL_MARKERS)
        ]
    return [ProviderModelEntryV1(id=model_id, label=model_id) for model_id in model_ids]


def _status(
    provider: str,
    row: AuthUserProviderCredentialRow | None,
) -> ProviderCredentialStatusV1:
    """The non-secret view of one stored credential. Never reads ``ciphertext``."""
    if row is None:
        return ProviderCredentialStatusV1(
            schema_version=PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
            provider=provider,
            configured=False,
        )
    return ProviderCredentialStatusV1(
        schema_version=PROVIDER_CREDENTIAL_STATUS_SCHEMA_VERSION,
        provider=provider,
        configured=True,
        key_hint=row.key_hint,
        verified_at=row.verified_at,
    )


@router.get("/provider-credentials", response_model=list[ProviderCredentialStatusV1])
async def list_provider_credentials(
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    uow: Annotated[PostgresUnitOfWork, Depends(provider_credential_uow)],
    registry: Annotated[ProviderRegistry, Depends(provider_registry)],
) -> list[ProviderCredentialStatusV1]:
    """Which cloud providers the caller has connected — status only, never key material.

    One entry per provider this deployment offers, connected or not, so the dialog can
    render the whole picker from a single answer.
    """
    rows = await uow.provider_credentials.list_status(actor.user_id)
    stored = {row.provider: row for row in rows}
    offered = _offered_provider_ids(registry)
    return [
        _status(kind.value, stored.get(kind.value))
        for kind, _ in LOADOUT_PROVIDER_OPTIONS
        if kind in CLOUD_PROVIDER_KINDS and kind.value in offered
    ]


@router.put(
    "/provider-credentials/{provider}",
    response_model=ProviderCredentialStatusV1,
    dependencies=[Depends(credential_write_guard)],
)
async def connect_provider_credential(
    provider: str,
    payload: ProviderCredentialConnectRequest,
    request: Request,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    uow: Annotated[PostgresUnitOfWork, Depends(provider_credential_uow)],
    registry: Annotated[ProviderRegistry, Depends(provider_registry)],
) -> ProviderCredentialStatusV1:
    """Verify an API key against its provider, then store it encrypted for this account.

    Verification comes first and the key is stored only if it worked, so a connected
    provider means a key the provider itself accepted — not one that will fail at
    launch. The encryption key is resolved before the provider is contacted: a
    deployment that cannot store the result should never have been sent the key at all.
    """
    _require_cloud_provider(provider, registry)
    encryption_key = _encryption_key(request)
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key must not be blank")

    await _verify_api_key(registry, provider, api_key=api_key)

    now = datetime.now(UTC)
    # The key was proven usable before verification, so this cannot fail on key material.
    ciphertext = encrypt_api_key(api_key, key=encryption_key)
    row = await uow.provider_credentials.upsert(
        user_id=actor.user_id,
        provider=provider,
        ciphertext=ciphertext,
        key_hint=derive_key_hint(api_key),
        verified_at=now,
        now=now,
    )
    return _status(provider, row)


@router.delete(
    "/provider-credentials/{provider}",
    status_code=204,
    dependencies=[Depends(credential_write_guard)],
)
async def disconnect_provider_credential(
    provider: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    uow: Annotated[PostgresUnitOfWork, Depends(provider_credential_uow)],
) -> Response:
    """Forget the caller's key for one provider.

    Idempotent, and takes no registry check: a provider the deployment stopped offering
    must still be disconnectable by whoever connected it.
    """
    await uow.provider_credentials.delete(actor.user_id, provider)
    return Response(status_code=204)


@router.get("/providers/loadout-options", response_model=list[LoadoutProviderOptionV1])
async def list_loadout_provider_options(
    _actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    registry: Annotated[ProviderRegistry, Depends(provider_registry)],
) -> list[LoadoutProviderOptionV1]:
    """The providers a run may be launched on, and which of them need a key first.

    Only providers this deployment actually registers are listed, so a narrowed egress
    allowlist removes the choice from the dialog instead of offering one that fails.
    """
    offered = _offered_provider_ids(registry)
    return [
        LoadoutProviderOptionV1(
            id=kind.value,
            label=label,
            requires_credential=kind in CLOUD_PROVIDER_KINDS,
        )
        for kind, label in LOADOUT_PROVIDER_OPTIONS
        if kind.value in offered
    ]


@router.get("/providers/{provider}/models", response_model=ProviderModelListV1)
async def list_provider_models(
    provider: str,
    request: Request,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    uow: Annotated[PostgresUnitOfWork, Depends(provider_credential_uow)],
    registry: Annotated[ProviderRegistry, Depends(provider_registry)],
    settings: Annotated[ProviderSettings, Depends(provider_runtime_settings)],
) -> ProviderModelListV1:
    """The models the caller may pick for a run on this provider.

    The local endpoint answers from configuration — it serves one loaded model, and
    asking it over the network would make the dialog wait on a model server that may be
    cold. Cloud providers answer live, on the caller's own decrypted key.
    """
    if provider == ProviderKind.OPENAI_COMPATIBLE.value:
        if provider not in _offered_provider_ids(registry):
            raise HTTPException(status_code=404, detail=f"Unknown model provider '{provider}'")
        local_model = settings.AEGIS_PROVIDER_LOCAL_MODEL
        return ProviderModelListV1(
            schema_version=PROVIDER_MODEL_LIST_SCHEMA_VERSION,
            provider=provider,
            models=[ProviderModelEntryV1(id=local_model, label=local_model)],
        )

    _require_cloud_provider(provider, registry)
    encryption_key = _encryption_key(request)
    try:
        api_key = await uow.provider_credentials.get_decrypted_api_key(
            actor.user_id, provider, encryption_key=encryption_key
        )
    except CredentialDecryptError as exc:
        # The stored key was written under a different encryption key, or was altered.
        # Either way it is unusable and the operator has to reconnect.
        raise HTTPException(
            status_code=400,
            detail=(
                f"The stored credential for '{provider}' could not be read. Reconnect the provider."
            ),
        ) from exc
    if api_key is None:
        raise HTTPException(
            status_code=400,
            detail=f"Connect an API key for '{provider}' before listing its models",
        )

    model_ids = await _fetch_model_ids(registry, provider, api_key=api_key)
    return ProviderModelListV1(
        schema_version=PROVIDER_MODEL_LIST_SCHEMA_VERSION,
        provider=provider,
        models=_selectable_models(provider, model_ids),
    )
