"""Composite fail-closed production startup validation."""

from __future__ import annotations

from aegis_contracts import AegisEnvironment, AegisSettings

from aegis_api.auth.startup import assert_secure_auth_configuration
from aegis_api.security.secrets import EnvironmentSecretProvider, SecretProvider

REQUIRED_PRODUCTION_VALUES = (
    "POSTGRES_HOST",
    "POSTGRES_PASSWORD",
    "REDIS_URL",
    "S3_ENDPOINT",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "AEGIS_OIDC_ISSUER",
    "AEGIS_OIDC_CLIENT_ID",
    "AEGIS_OIDC_CLIENT_SECRET",
    "AEGIS_OIDC_REDIRECT_URI",
    "AEGIS_CORS_ALLOWED_ORIGINS",
    "AEGIS_WEB_BASE_URL",
)

EXAMPLE_PLACEHOLDERS: dict[str, frozenset[str]] = {
    "POSTGRES_HOST": frozenset({"localhost", "127.0.0.1"}),
    "POSTGRES_PASSWORD": frozenset({"aegis", "aegis_dev"}),
    "REDIS_URL": frozenset(
        {"redis://localhost:6379/0", "redis://127.0.0.1:6379/0"}
    ),
    "S3_ENDPOINT": frozenset(
        {
            "http://localhost:9000",
            "http://localhost:9000/",
            "http://127.0.0.1:9000",
            "http://127.0.0.1:9000/",
        }
    ),
    "S3_ACCESS_KEY": frozenset({"aegis", "minio"}),
    "S3_SECRET_KEY": frozenset({"aegis_dev_secret", "minio123"}),
    "AEGIS_OIDC_CLIENT_SECRET": frozenset({"changeme", "change-me"}),
    "AEGIS_OIDC_REDIRECT_URI": frozenset(
        {
            "http://localhost:8000/api/v1/auth/callback",
            "http://127.0.0.1:8000/api/v1/auth/callback",
        }
    ),
    "AEGIS_CORS_ALLOWED_ORIGINS": frozenset(
        {
            "http://localhost:3000",
            "http://localhost:3000,http://127.0.0.1:3000",
        }
    ),
    "AEGIS_WEB_BASE_URL": frozenset(
        {"http://localhost:3000", "http://127.0.0.1:3000"}
    ),
}


class SecretConfigurationError(RuntimeError):
    """Raised without secret values when production configuration is unsafe."""


def assert_secure_startup_configuration(
    settings: AegisSettings,
    *,
    secret_provider: SecretProvider | None = None,
) -> None:
    """Validate auth plus required production secret/config values before I/O."""

    assert_secure_auth_configuration(settings)
    if settings.AEGIS_ENV != AegisEnvironment.PRODUCTION:
        return

    provider = secret_provider or EnvironmentSecretProvider(
        fallback=settings.model_dump()
    )
    missing: list[str] = []
    placeholders: list[str] = []
    for name in REQUIRED_PRODUCTION_VALUES:
        value = provider.get_secret(name)
        normalized = value.strip() if value is not None else ""
        if not normalized:
            missing.append(name)
            continue
        if normalized.lower() in EXAMPLE_PLACEHOLDERS.get(name, frozenset()):
            placeholders.append(name)

    if missing or placeholders:
        problems: list[str] = []
        if missing:
            problems.append("missing required values: " + ", ".join(sorted(missing)))
        if placeholders:
            problems.append(
                "development placeholders are forbidden: "
                + ", ".join(sorted(placeholders))
            )
        raise SecretConfigurationError(
            "Refusing to start with insecure production secret/configuration: "
            + "; ".join(problems)
        )
