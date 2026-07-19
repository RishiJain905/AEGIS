"""Bypass-oriented tests for the public HTTP trust boundary."""

from __future__ import annotations

from aegis_api.main import create_app
from aegis_api.security.middleware import TokenBucketRateLimitMiddleware
from aegis_contracts import AegisEnvironment, AegisSettings
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _settings(**overrides: object) -> AegisSettings:
    values: dict[str, object] = {
        "AEGIS_ENV": AegisEnvironment.TEST,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "aegis",
        "POSTGRES_USER": "aegis",
        "POSTGRES_PASSWORD": "test-password",
        "REDIS_URL": "redis://localhost:6379/0",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "test-access",
        "S3_SECRET_KEY": "test-secret",
        "S3_BUCKET": "aegis",
        "AEGIS_DEV_AUTH_ENABLED": False,
        "AEGIS_WS_ENABLED": False,
        "AEGIS_WS_DEV_AUTH_ENABLED": False,
        "AEGIS_OIDC_ENABLED": False,
        "AEGIS_CORS_ALLOWED_ORIGINS": "http://localhost:3000",
        "AEGIS_REQUEST_BODY_MAX_BYTES": 1024,
        "AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE": 60,
        "AEGIS_RATE_LIMIT_BURST": 10,
        "AEGIS_SECURITY_HSTS_ENABLED": False,
    }
    values.update(overrides)
    return AegisSettings(**values)  # type: ignore[arg-type]


def _client(settings: AegisSettings) -> TestClient:
    app: FastAPI = create_app(settings)

    async def probe() -> dict[str, bool]:
        return {"ok": True}

    app.add_api_route("/_security-probe", probe, methods=["GET", "POST"])
    return TestClient(app)


def test_api_responses_include_deny_by_default_security_headers() -> None:
    response = _client(_settings()).get("/_security-probe")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


def test_hsts_is_emitted_only_when_explicitly_enabled_in_production() -> None:
    response = _client(
        _settings(
            AEGIS_ENV=AegisEnvironment.PRODUCTION,
            AEGIS_SECURITY_HSTS_ENABLED=True,
            AEGIS_SECURITY_HSTS_MAX_AGE_SECONDS=86400,
        )
    ).get("/_security-probe")

    assert response.headers["strict-transport-security"] == (
        "max-age=86400; includeSubDomains"
    )


def test_declared_oversized_body_is_rejected_before_route_execution() -> None:
    response = _client(_settings(AEGIS_REQUEST_BODY_MAX_BYTES=16)).post(
        "/_security-probe",
        content=b'{"payload":"this is too large"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "schemaVersion": 1,
        "code": "REQUEST_BODY_TOO_LARGE",
        "message": "Request body exceeds the configured limit",
        "details": {"maxBytes": 16},
        "traceId": None,
    }


def test_token_bucket_rejects_burst_bypass_with_stable_error() -> None:
    client = _client(
        _settings(
            AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE=1,
            AEGIS_RATE_LIMIT_BURST=2,
        )
    )

    assert client.get("/_security-probe").status_code == 200
    assert client.get("/_security-probe").status_code == 200
    blocked = client.get("/_security-probe")

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert blocked.json()["details"] == {"limit": 1, "windowSeconds": 60}
    assert int(blocked.headers["retry-after"]) >= 1


def test_liveness_and_readiness_paths_are_exempt_from_rate_limit() -> None:
    client = _client(
        _settings(
            AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE=1,
            AEGIS_RATE_LIMIT_BURST=1,
        )
    )
    assert client.get("/_security-probe").status_code == 200
    assert client.get("/_security-probe").status_code == 429

    for path in ("/health", "/live"):
        assert client.get(path).status_code == 200


def test_rotating_session_cookie_cannot_bypass_ip_rate_limit() -> None:
    settings = _settings(
        AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE=1,
        AEGIS_RATE_LIMIT_BURST=1,
    )
    client = _client(settings)
    cookie_name = settings.AEGIS_SESSION_COOKIE_NAME

    client.cookies.set(cookie_name, "session-a")
    assert client.get("/_security-probe").status_code == 200
    client.cookies.set(cookie_name, "session-b")
    assert client.get("/_security-probe").status_code == 429


def test_rate_limiter_bounds_bucket_memory_with_deterministic_lru_eviction() -> None:
    async def downstream(*_args: object) -> None:
        return None

    limiter = TokenBucketRateLimitMiddleware(
        downstream,  # type: ignore[arg-type]
        session_cookie_name="aegis_session",
        requests_per_minute=60,
        burst=1,
        max_buckets=2,
        clock=lambda: 0.0,
    )
    limiter._consume("ip:one")
    limiter._consume("ip:two")
    limiter._consume("ip:three")

    assert list(limiter._buckets) == ["ip:two", "ip:three"]
