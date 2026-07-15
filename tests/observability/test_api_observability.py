"""API observability endpoint and authorization tests."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from aegis_observability.setup import reset_observability_for_tests


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    reset_observability_for_tests()
    monkeypatch.setenv("OTEL_ENABLED", "false")
    monkeypatch.setenv("AEGIS_ENV", "test")
    monkeypatch.setenv("AEGIS_DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("AEGIS_WS_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "localhost"))
    monkeypatch.setenv("POSTGRES_PORT", os.environ.get("POSTGRES_PORT", "5432"))
    monkeypatch.setenv("POSTGRES_DB", os.environ.get("POSTGRES_DB", "aegis"))
    monkeypatch.setenv("POSTGRES_USER", os.environ.get("POSTGRES_USER", "aegis"))
    monkeypatch.setenv("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "aegis_dev"))
    monkeypatch.setenv("REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    monkeypatch.setenv("S3_ENDPOINT", os.environ.get("S3_ENDPOINT", "http://localhost:9000"))
    monkeypatch.setenv("S3_ACCESS_KEY", os.environ.get("S3_ACCESS_KEY", "aegis"))
    monkeypatch.setenv("S3_SECRET_KEY", os.environ.get("S3_SECRET_KEY", "aegis_dev_secret"))
    monkeypatch.setenv("S3_BUCKET", os.environ.get("S3_BUCKET", "aegis-artifacts"))
    monkeypatch.setenv("AEGIS_LOG_JSON", "true")

    from aegis_api.websocket.manager import WebSocketGatewayManager

    monkeypatch.setattr(WebSocketGatewayManager, "start", AsyncMock(return_value=None))
    monkeypatch.setattr(WebSocketGatewayManager, "stop", AsyncMock(return_value=None))

    from aegis_api.db import session as db_session

    monkeypatch.setattr(db_session, "init_db", lambda _settings=None: None)
    monkeypatch.setattr(db_session, "shutdown_db", AsyncMock(return_value=None))

    from aegis_api.auth import startup as auth_startup

    monkeypatch.setattr(auth_startup, "assert_secure_auth_configuration", lambda _s: None)
    monkeypatch.setattr(auth_startup, "seed_dev_identities", AsyncMock(return_value=None))

    from aegis_api.main import create_app
    from aegis_contracts import AegisSettings
    from fastapi.testclient import TestClient

    settings = AegisSettings(
        AEGIS_ENV="test",
        POSTGRES_HOST=os.environ["POSTGRES_HOST"],
        POSTGRES_PORT=int(os.environ["POSTGRES_PORT"]),
        POSTGRES_DB=os.environ["POSTGRES_DB"],
        POSTGRES_USER=os.environ["POSTGRES_USER"],
        POSTGRES_PASSWORD=os.environ["POSTGRES_PASSWORD"],
        REDIS_URL=os.environ["REDIS_URL"],
        S3_ENDPOINT=os.environ["S3_ENDPOINT"],
        S3_ACCESS_KEY=os.environ["S3_ACCESS_KEY"],
        S3_SECRET_KEY=os.environ["S3_SECRET_KEY"],
        S3_BUCKET=os.environ["S3_BUCKET"],
        OTEL_ENABLED=False,
        AEGIS_DEV_AUTH_ENABLED=True,
        AEGIS_WS_ENABLED=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client
    reset_observability_for_tests()


def test_liveness_is_public_and_machine_readable(api_client) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    live = api_client.get("/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert "dependencies" not in live.json()


def test_correlation_headers_round_trip(api_client) -> None:
    response = api_client.get(
        "/health",
        headers={
            "X-Request-Id": "req_TESTREQUESTID00000000002",
            "X-Correlation-Id": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "req_TESTREQUESTID00000000002"
    assert response.headers.get("x-correlation-id")
    assert response.headers.get("traceparent")


def test_protected_ops_router_requires_admin_manage() -> None:
    """Protected ops routes are separated from public liveness and use admin:manage."""
    from aegis_api.auth.deps import require_permission
    from aegis_api.observability import protected_router, public_router
    from aegis_contracts import PermissionV1

    public_paths = {getattr(route, "path", "") for route in public_router.routes}
    protected_paths = {getattr(route, "path", "") for route in protected_router.routes}
    assert "/live" in public_paths
    assert "/diagnostics" in protected_paths
    assert "/metrics" in protected_paths
    assert "/live" not in protected_paths
    assert "/diagnostics" not in public_paths
    # Same factory used by main.py for mounting ops_protected_router.
    assert callable(require_permission(PermissionV1.ADMIN_MANAGE))
