"""Unit tests for the Phase 33 deployment smoke checks."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from scripts.deploy_smoke_test import (
    HttpResponse,
    SmokeCheckError,
    SmokeConfigurationError,
    check_health,
    check_migration_head,
    check_ready,
    check_unauthenticated_endpoint,
    check_websocket_endpoint,
    resolve_base_url,
)


@dataclass
class FakeTransport:
    responses: dict[str, HttpResponse]
    websocket_status: int = 101
    migration_head: str = "013_auth_identity"

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        _ = timeout_seconds
        return self.responses[url]

    def websocket_handshake(self, url: str, *, timeout_seconds: float) -> int:
        _ = url, timeout_seconds
        return self.websocket_status

    def read_migration_head(self, dsn: str, *, timeout_seconds: float) -> str:
        _ = dsn, timeout_seconds
        return self.migration_head


def _transport() -> FakeTransport:
    return FakeTransport(
        responses={
            "http://api.test/health": HttpResponse(
                status=200,
                payload={"status": "ok", "service": "api"},
            ),
            "http://api.test/ready": HttpResponse(
                status=200,
                payload={"status": "ready", "service": "api"},
            ),
            "http://api.test/api/v1/scenarios": HttpResponse(
                status=401,
                payload={"code": "UNAUTHORIZED"},
            ),
        }
    )


def test_smoke_checks_accept_healthy_vertical_slice() -> None:
    transport = _transport()

    check_health(transport, "http://api.test")
    check_ready(transport, "http://api.test")
    check_unauthenticated_endpoint(transport, "http://api.test")
    check_websocket_endpoint(transport, "ws://api.test/ws/v1/realtime")
    check_migration_head(
        transport,
        "postgresql://aegis:fake@localhost/aegis",
        expected_head="013_auth_identity",
    )


def test_unauthenticated_check_rejects_non_401_response() -> None:
    transport = _transport()
    transport.responses["http://api.test/api/v1/scenarios"] = HttpResponse(
        status=200,
        payload={},
    )

    with pytest.raises(SmokeCheckError, match="401"):
        check_unauthenticated_endpoint(transport, "http://api.test")


def test_staging_requires_explicit_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEGIS_STAGING_URL", raising=False)

    with pytest.raises(SmokeConfigurationError, match="AEGIS_STAGING_URL"):
        resolve_base_url("staging", None)


def test_local_base_url_accepts_values_loaded_from_env_file() -> None:
    assert (
        resolve_base_url("local", None, configured_url="http://127.0.0.1:18000")
        == "http://127.0.0.1:18000"
    )
