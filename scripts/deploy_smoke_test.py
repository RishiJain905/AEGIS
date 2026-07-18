"""Vertical deployment-readiness smoke test for a running AEGIS stack.

The script deliberately uses the Python standard library for HTTP and WebSocket
reachability checks.  The transport boundary is small and fakeable so the
contract can be tested without a running service or database.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import socket
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
DEFAULT_WS_PATH = "/ws/v1/realtime"
DEFAULT_PROTECTED_PATH = "/api/v1/scenarios"
DEFAULT_MIGRATION_HEAD = "013_auth_identity"


@dataclass(frozen=True)
class HttpResponse:
    """Decoded HTTP response used by the smoke checks and their fakes."""

    status: int
    payload: dict[str, object]


class SmokeCheckError(RuntimeError):
    """Raised when a running deployment fails a smoke check."""


class SmokeConfigurationError(RuntimeError):
    """Raised when a requested smoke environment is not configured."""


class SmokeTransport(Protocol):
    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse: ...

    def websocket_handshake(self, url: str, *, timeout_seconds: float) -> int: ...

    def read_migration_head(self, dsn: str, *, timeout_seconds: float) -> str: ...


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _require_status(response: HttpResponse, *, expected: int, check: str) -> None:
    if response.status != expected:
        raise SmokeCheckError(
            f"{check} returned HTTP {response.status}; expected HTTP {expected}"
        )


def check_health(transport: SmokeTransport, base_url: str) -> None:
    """Verify the process liveness endpoint responds with the API status."""

    response = transport.get(_url(base_url, "/health"), timeout_seconds=5.0)
    _require_status(response, expected=200, check="/health")
    if response.payload.get("status") != "ok":
        raise SmokeCheckError("/health did not report status=ok")


def check_ready(transport: SmokeTransport, base_url: str) -> None:
    """Verify required runtime dependencies are ready."""

    response = transport.get(_url(base_url, "/ready"), timeout_seconds=5.0)
    _require_status(response, expected=200, check="/ready")
    if response.payload.get("status") != "ready":
        raise SmokeCheckError("/ready did not report status=ready")


def check_unauthenticated_endpoint(
    transport: SmokeTransport,
    base_url: str,
    *,
    path: str = DEFAULT_PROTECTED_PATH,
) -> None:
    """Verify a representative protected route denies an anonymous request."""

    response = transport.get(_url(base_url, path), timeout_seconds=5.0)
    _require_status(response, expected=401, check=f"{path} unauthenticated")


def check_websocket_endpoint(transport: SmokeTransport, websocket_url: str) -> None:
    """Verify the WebSocket upgrade endpoint is reachable."""

    status = transport.websocket_handshake(websocket_url, timeout_seconds=5.0)
    if status != 101:
        raise SmokeCheckError(f"WebSocket upgrade returned HTTP {status}; expected HTTP 101")


def check_migration_head(
    transport: SmokeTransport,
    dsn: str,
    *,
    expected_head: str = DEFAULT_MIGRATION_HEAD,
) -> None:
    """Verify the database is at the expected Alembic head revision."""

    actual_head = transport.read_migration_head(dsn, timeout_seconds=5.0)
    if actual_head != expected_head:
        raise SmokeCheckError(
            f"database migration head is {actual_head!r}; expected {expected_head!r}"
        )


def resolve_base_url(
    environment: str,
    explicit_url: str | None,
    *,
    configured_url: str | None = None,
) -> str:
    """Resolve a local URL or require the explicit future staging URL."""

    if environment == "staging":
        configured = os.environ.get("AEGIS_STAGING_URL", "").strip()
        if not configured:
            raise SmokeConfigurationError(
                "staging smoke is disabled until AEGIS_STAGING_URL is configured"
            )
        return configured.rstrip("/")
    return (
        explicit_url
        or os.environ.get("AEGIS_LOCAL_URL")
        or configured_url
        or DEFAULT_LOCAL_URL
    ).rstrip("/")


def resolve_websocket_url(base_url: str, configured_url: str | None = None) -> str:
    """Derive the default WebSocket URL from the HTTP API URL."""

    configured = (os.environ.get("AEGIS_LOCAL_WS_URL") or configured_url or "").strip()
    if configured:
        return configured
    parsed = urlsplit(base_url)
    scheme = {"http": "ws", "https": "wss"}.get(parsed.scheme)
    if scheme is None or not parsed.netloc:
        raise SmokeConfigurationError("base URL must use http:// or https://")
    return f"{scheme}://{parsed.netloc}{DEFAULT_WS_PATH}"


def load_env_file(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE entries without mutating the process environment."""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name.strip()] = value
    return values


def resolve_postgres_dsn(
    environment: str,
    values: dict[str, str],
    explicit_dsn: str | None,
) -> str:
    """Resolve a host-accessible PostgreSQL DSN without logging its password."""

    if explicit_dsn:
        return explicit_dsn
    if environment == "staging":
        configured = os.environ.get("AEGIS_STAGING_POSTGRES_URL", "").strip()
        if not configured:
            raise SmokeConfigurationError(
                "staging smoke requires AEGIS_STAGING_POSTGRES_URL for the migration check"
            )
        return configured

    smoke_dsn = os.environ.get("AEGIS_SMOKE_POSTGRES_URL", "").strip()
    if smoke_dsn:
        return smoke_dsn

    host = values.get("POSTGRES_HOST", "127.0.0.1")
    port = values.get("POSTGRES_PORT", "5432")
    if host in {"postgres", "db"}:
        host = "127.0.0.1"
        port = values.get("AEGIS_SMOKE_POSTGRES_PORT", "55432")
    user = quote(values.get("POSTGRES_USER", "aegis"), safe="")
    password = quote(values.get("POSTGRES_PASSWORD", ""), safe="")
    database = quote(values.get("POSTGRES_DB", "aegis"), safe="")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


class UrllibSmokeTransport:
    """Real transport used by the command-line smoke test."""

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return self._decode_response(response.status, response.read())
        except HTTPError as exc:
            return self._decode_response(exc.code, exc.read())
        except URLError as exc:
            raise SmokeCheckError(f"HTTP check could not reach {url}: {exc.reason}") from exc

    @staticmethod
    def _decode_response(status: int, raw_body: bytes) -> HttpResponse:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeCheckError("HTTP check returned a non-JSON response") from exc
        if not isinstance(payload, dict):
            raise SmokeCheckError("HTTP check returned a non-object JSON response")
        return HttpResponse(status=status, payload=payload)

    def websocket_handshake(self, url: str, *, timeout_seconds: float) -> int:
        parsed = urlsplit(url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise SmokeConfigurationError("WebSocket URL must use ws:// or wss://")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: websocket\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Key: {key}\r\n\r\n"
        ).encode("ascii")
        raw_response = bytearray()
        try:
            with socket.create_connection(
                (parsed.hostname, port), timeout=timeout_seconds
            ) as connection:
                if parsed.scheme == "wss":
                    context = ssl.create_default_context()
                    with context.wrap_socket(connection, server_hostname=parsed.hostname) as tls:
                        tls.sendall(request)
                        raw_response.extend(self._read_headers(tls))
                else:
                    connection.sendall(request)
                    raw_response.extend(self._read_headers(connection))
        except (OSError, ssl.SSLError) as exc:
            raise SmokeCheckError(f"WebSocket check could not reach {url}") from exc
        first_line = bytes(raw_response).split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = first_line.split(" ", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise SmokeCheckError("WebSocket endpoint returned an invalid HTTP response")
        return int(parts[1])

    @staticmethod
    def _read_headers(connection: socket.socket) -> bytes:
        response = bytearray()
        while b"\r\n\r\n" not in response and len(response) < 16_384:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
        return bytes(response)

    def read_migration_head(self, dsn: str, *, timeout_seconds: float) -> str:
        try:
            import psycopg

            with (
                psycopg.connect(dsn, connect_timeout=max(1, int(timeout_seconds))) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("SELECT version_num FROM alembic_version")
                row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001 - preserve a secret-free smoke error
            raise SmokeCheckError(
                f"database migration head query failed: {type(exc).__name__}"
            ) from exc
        if not row or not isinstance(row[0], str):
            raise SmokeCheckError("database migration head query returned no revision")
        return row[0]


def _default_env_file() -> Path | None:
    for candidate in (Path(".env.production"), Path(".env")):
        if candidate.exists():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("local", "staging"), default="local")
    parser.add_argument("--base-url", help="Local API base URL; staging uses AEGIS_STAGING_URL")
    parser.add_argument("--env-file", type=Path, help="Environment file used for local DB settings")
    parser.add_argument(
        "--postgres-url",
        help="Host-accessible PostgreSQL URL for the migration check",
    )
    parser.add_argument("--expected-migration-head", default=DEFAULT_MIGRATION_HEAD)
    args = parser.parse_args(argv)

    try:
        env_file = args.env_file or _default_env_file()
        values = load_env_file(env_file) if env_file else {}
        base_url = resolve_base_url(
            args.environment,
            args.base_url,
            configured_url=values.get("AEGIS_LOCAL_URL"),
        )
        transport = UrllibSmokeTransport()
        checks: tuple[tuple[str, Callable[[], None]], ...] = (
            ("health", lambda: check_health(transport, base_url)),
            ("ready", lambda: check_ready(transport, base_url)),
            (
                "unauthenticated",
                lambda: check_unauthenticated_endpoint(transport, base_url),
            ),
            (
                "websocket",
                lambda: check_websocket_endpoint(
                    transport,
                    resolve_websocket_url(base_url, values.get("AEGIS_LOCAL_WS_URL")),
                ),
            ),
            (
                "migration",
                lambda: check_migration_head(
                    transport,
                    resolve_postgres_dsn(args.environment, values, args.postgres_url),
                    expected_head=args.expected_migration_head,
                ),
            ),
        )
        for name, check in checks:
            check()
            print(f"PASS {name}")
    except SmokeConfigurationError as exc:
        print(f"REFUSED: {exc}")
        return 2
    except SmokeCheckError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("DEPLOY SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
