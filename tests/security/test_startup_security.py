"""Fail-closed production configuration and shared-redaction tests."""

from __future__ import annotations

import pytest
from aegis_api.security.secrets import EnvironmentSecretProvider
from aegis_api.security.startup import (
    SecretConfigurationError,
    assert_secure_startup_configuration,
)
from aegis_contracts import AegisEnvironment, AegisSettings
from aegis_model_provider import redaction as provider_redaction
from aegis_observability import redaction as observability_redaction
from pydantic import ValidationError


def _production_settings(**overrides: object) -> AegisSettings:
    values: dict[str, object] = {
        "AEGIS_ENV": AegisEnvironment.PRODUCTION,
        "POSTGRES_HOST": "db.internal",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "aegis",
        "POSTGRES_USER": "aegis_runtime",
        "POSTGRES_PASSWORD": "prod-db-secret-value",
        "REDIS_URL": "rediss://redis.internal:6379/0",
        "S3_ENDPOINT": "https://objects.internal",
        "S3_ACCESS_KEY": "prod-object-access",
        "S3_SECRET_KEY": "prod-object-secret-value",
        "S3_BUCKET": "aegis-artifacts",
        "AEGIS_DEV_AUTH_ENABLED": False,
        "AEGIS_WS_DEV_AUTH_ENABLED": False,
        "AEGIS_OIDC_ENABLED": True,
        "AEGIS_OIDC_ISSUER": "https://id.example.test",
        "AEGIS_OIDC_CLIENT_ID": "aegis-production",
        "AEGIS_OIDC_CLIENT_SECRET": "prod-oidc-secret-value",
        "AEGIS_OIDC_REDIRECT_URI": "https://aegis.example.test/api/v1/auth/callback",
        "AEGIS_CORS_ALLOWED_ORIGINS": "https://aegis.example.test",
        "AEGIS_WEB_BASE_URL": "https://aegis.example.test",
    }
    values.update(overrides)
    return AegisSettings(**values)  # type: ignore[arg-type]


def _provider(settings: AegisSettings) -> EnvironmentSecretProvider:
    return EnvironmentSecretProvider(environ={}, fallback=settings.model_dump())


def test_production_accepts_non_placeholder_required_secrets() -> None:
    settings = _production_settings()
    assert_secure_startup_configuration(settings, secret_provider=_provider(settings))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("S3_ACCESS_KEY", ""),
        ("S3_SECRET_KEY", ""),
        ("AEGIS_OIDC_CLIENT_SECRET", ""),
        ("POSTGRES_PASSWORD", "aegis_dev"),
        ("S3_SECRET_KEY", "aegis_dev_secret"),
    ],
)
def test_production_rejects_missing_or_example_secrets(name: str, value: str) -> None:
    settings = _production_settings(**{name: value})

    with pytest.raises(SecretConfigurationError) as exc:
        assert_secure_startup_configuration(settings, secret_provider=_provider(settings))

    assert name in str(exc.value)
    assert "prod-db-secret-value" not in str(exc.value)
    assert "prod-object-secret-value" not in str(exc.value)
    assert "prod-oidc-secret-value" not in str(exc.value)


def test_secret_provider_prefers_process_environment_over_fallback() -> None:
    provider = EnvironmentSecretProvider(
        environ={"TOKEN": "from-environment"},
        fallback={"TOKEN": "from-fallback"},
    )
    assert provider.get_secret("TOKEN") == "from-environment"


def test_settings_reject_blank_database_secret_before_startup() -> None:
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD must not be blank"):
        _production_settings(POSTGRES_PASSWORD="")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("POSTGRES_HOST", "localhost"),
        ("REDIS_URL", "redis://localhost:6379/0"),
        ("S3_ENDPOINT", "http://localhost:9000"),
        ("AEGIS_OIDC_REDIRECT_URI", "http://localhost:8000/api/v1/auth/callback"),
        ("AEGIS_WEB_BASE_URL", "http://localhost:3000"),
    ],
)
def test_production_rejects_example_local_service_configuration(
    name: str,
    value: str,
) -> None:
    settings = _production_settings(**{name: value})
    with pytest.raises(SecretConfigurationError) as exc:
        assert_secure_startup_configuration(settings, secret_provider=_provider(settings))
    assert name in str(exc.value)


def test_observability_reuses_model_provider_redaction_implementation() -> None:
    assert observability_redaction.redact_mapping is provider_redaction.redact_mapping
    assert observability_redaction.redact_headers is provider_redaction.redact_headers
    payload = {
        "authorization": "Bearer token-value",
        "nested": {"password": "do-not-log", "message": "safe"},
    }
    redacted = observability_redaction.redact_mapping(payload)
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"] == {"password": "[REDACTED]", "message": "safe"}
