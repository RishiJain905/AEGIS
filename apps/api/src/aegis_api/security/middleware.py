"""Fail-closed ASGI controls for the public API boundary."""

from __future__ import annotations

import hashlib
import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from http.cookies import SimpleCookie

from aegis_contracts import AegisEnvironment, ApiErrorEnvelopeV1
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'; object-src 'none'"
)
RATE_LIMIT_EXEMPT_PATHS = frozenset({"/health", "/live", "/ready"})


def _trace_id(headers: Headers) -> str | None:
    traceparent = headers.get("traceparent", "")
    parts = traceparent.split("-")
    if len(parts) == 4 and len(parts[1]) == 32:
        return parts[1]
    return headers.get("x-request-id")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object],
    headers: Headers,
    response_headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=code,
        message=message,
        details=details,
        trace_id=_trace_id(headers),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(by_alias=True, mode="json"),
        headers=response_headers,
    )


class SecurityHeadersMiddleware:
    """Apply response hardening consistently, including middleware errors."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        environment: AegisEnvironment,
        hsts_enabled: bool,
        hsts_max_age_seconds: int,
    ) -> None:
        self._app = app
        self._hsts_enabled = (
            environment == AegisEnvironment.PRODUCTION and hsts_enabled
        )
        self._hsts_value = f"max-age={hsts_max_age_seconds}; includeSubDomains"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = API_CONTENT_SECURITY_POLICY
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if self._hsts_enabled:
                    headers["Strict-Transport-Security"] = self._hsts_value
                elif "strict-transport-security" in headers:
                    del headers["strict-transport-security"]
            await send(message)

        await self._app(scope, receive, send_with_headers)


class RequestBodyLimitMiddleware:
    """Bound request bodies even when Content-Length is absent or dishonest."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                response = _error_response(
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message="Content-Length must be a non-negative integer",
                    details={},
                    headers=headers,
                )
                await response(scope, receive, send)
                return
            if declared_bytes < 0:
                response = _error_response(
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message="Content-Length must be a non-negative integer",
                    details={},
                    headers=headers,
                )
                await response(scope, receive, send)
                return
            if declared_bytes > self._max_bytes:
                await self._reject(scope, receive, send, headers)
                return

        buffered: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            received_bytes += len(message.get("body", b""))
            if received_bytes > self._max_bytes:
                await self._reject(scope, receive, send, headers)
                return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> Message:
            if buffered:
                return buffered.pop(0)
            return {"type": "http.disconnect"}

        await self._app(scope, replay_receive, send)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        headers: Headers,
    ) -> None:
        response = _error_response(
            status_code=413,
            code="REQUEST_BODY_TOO_LARGE",
            message="Request body exceeds the configured limit",
            details={"maxBytes": self._max_bytes},
            headers=headers,
        )
        await response(scope, receive, send)


@dataclass(slots=True)
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketRateLimitMiddleware:
    """Deterministic in-process token bucket keyed by hashed session or client IP."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_cookie_name: str,
        requests_per_minute: int,
        burst: int,
        max_buckets: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._app = app
        self._session_cookie_name = session_cookie_name
        self._requests_per_minute = requests_per_minute
        self._capacity = float(burst)
        self._refill_per_second = requests_per_minute / 60.0
        self._max_buckets = max_buckets
        self._clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in RATE_LIMIT_EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        retry_after = 0.0
        for key in self._keys(scope, headers):
            allowed, key_retry_after = self._consume(key)
            retry_after = max(retry_after, key_retry_after)
            if not allowed:
                break
        if retry_after > 0.0:
            response = _error_response(
                status_code=429,
                code="RATE_LIMIT_EXCEEDED",
                message="Request rate limit exceeded",
                details={"limit": self._requests_per_minute, "windowSeconds": 60},
                headers=headers,
                response_headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _consume(self, key: str) -> tuple[bool, float]:
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_buckets:
                self._buckets.popitem(last=False)
            bucket = _Bucket(tokens=self._capacity, last_refill=now)
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(
            self._capacity,
            bucket.tokens + elapsed * self._refill_per_second,
        )
        bucket.last_refill = now
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0.0
        return False, (1.0 - bucket.tokens) / self._refill_per_second

    def _keys(self, scope: Scope, headers: Headers) -> list[str]:
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        keys = [f"ip:{client_ip}"]
        raw_cookie = headers.get("cookie", "")
        cookie = SimpleCookie()
        try:
            cookie.load(raw_cookie)
        except Exception:  # malformed cookie input falls back to the IP bucket
            cookie.clear()
        session = cookie.get(self._session_cookie_name)
        if session is not None and session.value:
            digest = hashlib.sha256(session.value.encode("utf-8")).hexdigest()
            keys.append(f"session:{digest}")
        return keys
