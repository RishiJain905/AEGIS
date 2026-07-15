"""Auth startup guards and development identity seeding."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import AegisEnvironment, AegisSettings
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_api.auth.service import DEV_SEED_USERS
from aegis_api.db.session import get_db_session_maker


class InsecureAuthConfigurationError(RuntimeError):
    """Raised when production would start with insecure development auth."""


def assert_secure_auth_configuration(settings: AegisSettings) -> None:
    if settings.AEGIS_ENV != AegisEnvironment.PRODUCTION:
        return
    problems: list[str] = []
    if settings.AEGIS_DEV_AUTH_ENABLED:
        problems.append("AEGIS_DEV_AUTH_ENABLED must be false in production")
    if settings.AEGIS_WS_DEV_AUTH_ENABLED:
        problems.append("AEGIS_WS_DEV_AUTH_ENABLED must be false in production")
    if not settings.AEGIS_OIDC_ENABLED:
        problems.append("AEGIS_OIDC_ENABLED must be true in production")
    if not settings.cors_allowed_origins:
        problems.append("AEGIS_CORS_ALLOWED_ORIGINS must list explicit origins")
    if "*" in settings.cors_allowed_origins:
        problems.append("AEGIS_CORS_ALLOWED_ORIGINS must not include wildcard origins")
    if problems:
        raise InsecureAuthConfigurationError(
            "Refusing to start with insecure authentication configuration: "
            + "; ".join(problems)
        )


async def seed_dev_identities(settings: AegisSettings) -> None:
    if settings.AEGIS_ENV == AegisEnvironment.PRODUCTION:
        return
    if not settings.AEGIS_DEV_AUTH_ENABLED:
        return
    now = datetime.now(tz=UTC)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        for user_id, display_name, roles in DEV_SEED_USERS:
            await uow.auth.upsert_user(
                user_id=user_id,
                display_name=display_name,
                roles=roles,
                now=now,
            )
