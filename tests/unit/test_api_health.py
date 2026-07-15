"""FastAPI application tests."""

import os
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from aegis_api.main import create_app
from aegis_contracts import AegisEnvironment, AegisSettings, LogLevel
from aegis_contracts.observability import DependencyStateV1
from aegis_observability.health import DependencyProbeResult
from fastapi.testclient import TestClient


def _probe(
    name: str,
    *,
    state: DependencyStateV1 = DependencyStateV1.OK,
    required: bool = True,
    latency_ms: float = 1.0,
) -> DependencyProbeResult:
    return DependencyProbeResult(
        name=name,
        state=state,
        required=required,
        latency_ms=latency_ms,
        message=None if state == DependencyStateV1.OK else f"{name} unavailable",
    )


def _ok_probes() -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    return (
        AsyncMock(return_value=_probe("postgres")),
        AsyncMock(return_value=_probe("redis")),
        AsyncMock(
            return_value=_probe(
                "object_storage",
                required=False,
                state=DependencyStateV1.OK,
            )
        ),
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    env = {
        "AEGIS_ENV": "test",
        "LOG_LEVEL": "info",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "aegis",
        "POSTGRES_USER": "aegis",
        "POSTGRES_PASSWORD": "aegis_dev",
        "REDIS_URL": "redis://localhost:6379/0",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "aegis",
        "S3_SECRET_KEY": "aegis_dev_secret",
        "S3_BUCKET": "aegis-artifacts",
        "API_PORT": "8000",
        "WEB_PORT": "3000",
        "AEGIS_READY_REQUIRE_REDIS": "true",
        "AEGIS_READY_REQUIRE_OBJECT_STORAGE": "false",
    }
    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    settings = AegisSettings(
        AEGIS_ENV=AegisEnvironment.TEST,
        LOG_LEVEL=LogLevel.INFO,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="aegis_dev",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="aegis",
        S3_SECRET_KEY="aegis_dev_secret",
        S3_BUCKET="aegis-artifacts",
        API_PORT=8000,
        WEB_PORT=3000,
        AEGIS_WS_ENABLED=False,
        # Health unit tests do not provide PostgreSQL; skip identity seeding.
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_READY_REQUIRE_REDIS=True,
        AEGIS_READY_REQUIRE_OBJECT_STORAGE=False,
    )
    postgres, redis, object_storage = _ok_probes()
    with (
        patch("aegis_api.observability.routes.check_postgres_bounded", new=postgres),
        patch("aegis_api.observability.routes.check_redis_bounded", new=redis),
        patch("aegis_api.observability.routes.check_object_storage", new=object_storage),
    ):
        app = create_app(settings=settings)
        with TestClient(app) as test_client:
            yield test_client
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "api"


def test_live_endpoint(client: TestClient) -> None:
    response = client.get("/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == 1
    assert payload["status"] == "ok"
    assert payload["service"] == "api"
    assert "checkedAt" in payload


def test_ready_endpoint(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == 1
    assert payload["status"] == "ready"
    assert payload["environment"] == "test"
    assert payload["service"] == "api"
    names = {dep["name"]: dep["state"] for dep in payload["dependencies"]}
    assert names["postgres"] == "ok"
    assert names["redis"] == "ok"


def test_ready_endpoint_fails_closed_when_database_unavailable() -> None:
    settings = AegisSettings(
        AEGIS_ENV=AegisEnvironment.TEST,
        LOG_LEVEL=LogLevel.INFO,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="aegis_dev",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="aegis",
        S3_SECRET_KEY="aegis_dev_secret",
        S3_BUCKET="aegis-artifacts",
        API_PORT=8000,
        WEB_PORT=3000,
        AEGIS_WS_ENABLED=False,
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_READY_REQUIRE_REDIS=True,
        AEGIS_READY_REQUIRE_OBJECT_STORAGE=False,
    )
    postgres = AsyncMock(
        return_value=_probe("postgres", state=DependencyStateV1.UNAVAILABLE)
    )
    redis = AsyncMock(return_value=_probe("redis"))
    object_storage = AsyncMock(
        return_value=_probe("object_storage", required=False, state=DependencyStateV1.OK)
    )
    with (
        patch("aegis_api.observability.routes.check_postgres_bounded", new=postgres),
        patch("aegis_api.observability.routes.check_redis_bounded", new=redis),
        patch("aegis_api.observability.routes.check_object_storage", new=object_storage),
    ):
        app = create_app(settings=settings)
        with TestClient(app) as test_client:
            response = test_client.get("/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    deps = {dep["name"]: dep for dep in payload["dependencies"]}
    assert deps["postgres"]["state"] == "unavailable"
