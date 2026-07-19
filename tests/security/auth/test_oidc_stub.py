"""Tests for the fail-closed OIDC stub and bounded OIDC login-state store.

Covers AEGIS-OITB-002 (production token exchange is a fail-closed stub with a
descriptive error and an honest provider factory) and AEGIS-OITB-005 (pending
OIDC state is bounded by TTL and capacity).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from aegis_api.auth import router as auth_router
from aegis_api.auth.oidc import (
    AuthOidcError,
    ConfiguredOidcProvider,
    create_oidc_provider,
)
from aegis_contracts import AegisEnvironment, AegisSettings


def _settings(**overrides: object) -> AegisSettings:
    base = {
        "AEGIS_ENV": AegisEnvironment.PRODUCTION,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "aegis",
        "POSTGRES_USER": "aegis",
        "POSTGRES_PASSWORD": "aegis",
        "REDIS_URL": "redis://localhost:6379/0",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "minio",
        "S3_SECRET_KEY": "minio123",
        "S3_BUCKET": "aegis",
        "AEGIS_DEV_AUTH_ENABLED": False,
        "AEGIS_WS_DEV_AUTH_ENABLED": False,
        "AEGIS_OIDC_ENABLED": True,
        "AEGIS_OIDC_ISSUER": "https://idp.example.test",
        "AEGIS_OIDC_CLIENT_ID": "aegis-client",
        "AEGIS_CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    }
    base.update(overrides)
    return AegisSettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_exchange_code_fails_closed_with_descriptive_error() -> None:
    provider = ConfiguredOidcProvider(_settings())
    with pytest.raises(AuthOidcError) as exc:
        await provider.exchange_code(code="abc", code_verifier="v")
    message = exc.value.message
    assert "not implemented" in message.lower()
    assert "v1.0" in message


def test_create_oidc_provider_returns_configured_when_enabled() -> None:
    provider = create_oidc_provider(_settings(AEGIS_OIDC_ENABLED=True))
    assert isinstance(provider, ConfiguredOidcProvider)


def test_create_oidc_provider_raises_when_disabled() -> None:
    # The previously dead branch silently returned a stub; it must now be honest.
    with pytest.raises(AuthOidcError):
        create_oidc_provider(
            _settings(AEGIS_ENV=AegisEnvironment.DEVELOPMENT, AEGIS_OIDC_ENABLED=False)
        )


@pytest.fixture(autouse=True)
def _clear_oidc_state() -> Iterator[None]:
    auth_router._OIDC_STATE.clear()
    yield
    auth_router._OIDC_STATE.clear()


def _put_state(key: str, created_at: datetime) -> None:
    auth_router._OIDC_STATE[key] = {
        "nonce": f"nonce-{key}",
        "verifier": f"verifier-{key}",
        "created_at": created_at.isoformat(),
    }


def test_prune_evicts_states_older_than_ttl() -> None:
    now = datetime.now(tz=UTC)
    fresh = now - timedelta(seconds=10)
    stale = now - timedelta(seconds=auth_router._OIDC_STATE_TTL_SECONDS + 60)
    _put_state("fresh", fresh)
    _put_state("stale", stale)

    auth_router._prune_oidc_state(now=now)

    assert "fresh" in auth_router._OIDC_STATE
    assert "stale" not in auth_router._OIDC_STATE


def test_prune_caps_capacity_evicting_oldest_first() -> None:
    now = datetime.now(tz=UTC)
    total = auth_router._OIDC_STATE_MAX_ENTRIES + 25
    for index in range(total):
        # Older entries have smaller index (further in the past).
        _put_state(f"state-{index:04d}", now - timedelta(seconds=total - index))

    auth_router._prune_oidc_state(now=now)

    assert len(auth_router._OIDC_STATE) == auth_router._OIDC_STATE_MAX_ENTRIES
    # The oldest entries are evicted; the newest are retained.
    assert "state-0000" not in auth_router._OIDC_STATE
    assert f"state-{total - 1:04d}" in auth_router._OIDC_STATE
