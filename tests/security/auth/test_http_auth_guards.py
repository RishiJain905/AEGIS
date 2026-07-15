"""HTTP auth guard unit checks that do not require a live database."""

from __future__ import annotations

import pytest
from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_api.main import create_app
from aegis_contracts import AegisEnvironment, AegisSettings, AuthErrorCode
from fastapi.testclient import TestClient


def _settings() -> AegisSettings:
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
    )


def test_cors_allows_configured_origin_only() -> None:
    # Exercise CORS middleware without starting Redis/Postgres-backed lifespan work.
    app = create_app(_settings())
    client = TestClient(app)
    allowed = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    denied = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.headers.get("access-control-allow-origin") != "https://evil.example"


@pytest.mark.asyncio
async def test_auth_service_rejects_missing_and_tampered_tokens() -> None:
    service = AuthService(session_ttl_seconds=60)

    class _FakeAuth:
        async def get_session_by_token_hash(self, token_hash: str):  # noqa: ANN001
            _ = token_hash
            return None

    class _FakeUow:
        auth = _FakeAuth()

    with pytest.raises(AuthServiceError) as missing:
        await service.resolve_actor_from_token(_FakeUow(), raw_token=None)  # type: ignore[arg-type]
    assert missing.value.code == AuthErrorCode.UNAUTHENTICATED

    with pytest.raises(AuthServiceError) as tampered:
        await service.resolve_actor_from_token(_FakeUow(), raw_token="tampered")  # type: ignore[arg-type]
    assert tampered.value.code == AuthErrorCode.UNAUTHENTICATED
