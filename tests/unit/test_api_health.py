"""FastAPI application tests."""

import os
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from aegis_api.main import create_app
from aegis_contracts import AegisEnvironment, AegisSettings, LogLevel
from fastapi.testclient import TestClient


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
    )
    with patch("aegis_api.main.check_postgres", new=AsyncMock(return_value=True)):
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


def test_ready_endpoint(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["environment"] == "test"
    assert payload["database"] == "ok"


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
    )
    with patch("aegis_api.main.check_postgres", new=AsyncMock(return_value=False)):
        app = create_app(settings=settings)
        with TestClient(app) as test_client:
            response = test_client.get("/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"] == "unavailable"
