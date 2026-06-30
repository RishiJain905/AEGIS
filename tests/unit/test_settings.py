"""Settings validation tests."""

import os
from collections.abc import Iterator

import pytest
from aegis_contracts import AegisSettings, load_settings
from pydantic import ValidationError


@pytest.fixture
def valid_env() -> Iterator[None]:
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
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_load_settings_accepts_valid_env(valid_env: None) -> None:
    settings = load_settings()
    assert settings.AEGIS_ENV.value == "test"
    assert settings.API_PORT == 8000


def test_settings_reject_blank_password(valid_env: None) -> None:
    os.environ["POSTGRES_PASSWORD"] = "   "
    with pytest.raises(ValidationError):
        AegisSettings()


def test_settings_reject_invalid_redis_url(valid_env: None) -> None:
    os.environ["REDIS_URL"] = "not-a-url"
    with pytest.raises(ValidationError):
        AegisSettings()
