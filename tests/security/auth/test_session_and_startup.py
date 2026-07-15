"""Unit tests for auth tokens, CSRF, and production fail-closed startup."""

from __future__ import annotations

import pytest
from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_api.auth.startup import InsecureAuthConfigurationError, assert_secure_auth_configuration
from aegis_api.auth.tokens import constant_time_equals, generate_opaque_token, hash_token
from aegis_contracts import AegisEnvironment, AegisSettings, AuthErrorCode


def _settings(**overrides: object) -> AegisSettings:
    base = {
        "AEGIS_ENV": AegisEnvironment.DEVELOPMENT,
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
        "AEGIS_DEV_AUTH_ENABLED": True,
        "AEGIS_WS_DEV_AUTH_ENABLED": True,
        "AEGIS_OIDC_ENABLED": False,
        "AEGIS_CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    }
    base.update(overrides)
    return AegisSettings(**base)  # type: ignore[arg-type]


def test_token_hash_is_stable_and_one_way() -> None:
    token = generate_opaque_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


def test_csrf_validation_rejects_mismatch() -> None:
    service = AuthService(session_ttl_seconds=60)
    with pytest.raises(AuthServiceError) as exc:
        service.validate_csrf(session_csrf="csrf_expected_value_xx", header_csrf="csrf_other")
    assert exc.value.code == AuthErrorCode.CSRF_FAILED


def test_csrf_validation_accepts_match() -> None:
    service = AuthService(session_ttl_seconds=60)
    service.validate_csrf(
        session_csrf="csrf_expected_value_xx",
        header_csrf="csrf_expected_value_xx",
    )


def test_constant_time_equals() -> None:
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")


def test_production_rejects_dev_auth() -> None:
    settings = _settings(
        AEGIS_ENV=AegisEnvironment.PRODUCTION,
        AEGIS_DEV_AUTH_ENABLED=True,
        AEGIS_WS_DEV_AUTH_ENABLED=False,
        AEGIS_OIDC_ENABLED=True,
    )
    with pytest.raises(InsecureAuthConfigurationError):
        assert_secure_auth_configuration(settings)


def test_production_rejects_ws_dev_auth() -> None:
    settings = _settings(
        AEGIS_ENV=AegisEnvironment.PRODUCTION,
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_DEV_AUTH_ENABLED=True,
        AEGIS_OIDC_ENABLED=True,
    )
    with pytest.raises(InsecureAuthConfigurationError):
        assert_secure_auth_configuration(settings)


def test_production_requires_oidc() -> None:
    settings = _settings(
        AEGIS_ENV=AegisEnvironment.PRODUCTION,
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_DEV_AUTH_ENABLED=False,
        AEGIS_OIDC_ENABLED=False,
    )
    with pytest.raises(InsecureAuthConfigurationError):
        assert_secure_auth_configuration(settings)


def test_production_rejects_wildcard_cors() -> None:
    settings = _settings(
        AEGIS_ENV=AegisEnvironment.PRODUCTION,
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_DEV_AUTH_ENABLED=False,
        AEGIS_OIDC_ENABLED=True,
        AEGIS_CORS_ALLOWED_ORIGINS="*",
    )
    with pytest.raises(InsecureAuthConfigurationError):
        assert_secure_auth_configuration(settings)


def test_development_allows_dev_auth() -> None:
    settings = _settings()
    assert_secure_auth_configuration(settings)


@pytest.mark.asyncio
async def test_seed_dev_identities_skips_connection_errors_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegis_api.auth import startup as startup_module

    class _Boom:
        async def __aenter__(self):  # noqa: ANN204
            raise OSError("simulated postgres unavailable")

        async def __aexit__(self, *args: object) -> None:
            _ = args

    monkeypatch.setattr(
        startup_module,
        "PostgresUnitOfWork",
        lambda *_args, **_kwargs: _Boom(),
    )
    settings = _settings(AEGIS_ENV=AegisEnvironment.TEST, AEGIS_DEV_AUTH_ENABLED=True)
    await startup_module.seed_dev_identities(settings)
