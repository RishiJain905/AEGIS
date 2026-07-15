"""FastAPI/Starlette middleware helpers for correlation and tracing."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aegis_contracts.observability import ActorKindV1, LogOutcomeV1

from aegis_observability.context import (
    TelemetryContextState,
    bind_context,
    clear_context,
    extract_headers,
    merge_context,
    propagate_headers,
)
from aegis_observability.logging import get_logger
from aegis_observability.metrics import get_metrics
from aegis_observability.setup import get_runtime


def _route_group(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "root"
    if parts[0] == "api" and len(parts) > 2:
        return parts[2]
    if parts[0] in {"health", "ready", "live", "diagnostics", "metrics"}:
        return parts[0]
    return parts[0][:32]


def create_observability_middleware(service_name: str = "aegis-api") -> Any:
    """Return a Starlette/FastAPI middleware class bound to service_name."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class ObservabilityMiddleware(BaseHTTPMiddleware):
        async def dispatch(
            self,
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            header_map = {k: v for k, v in request.headers.items()}
            ctx = extract_headers(header_map)
            ctx = ctx.with_updates(
                service=service_name,
                operation="http.request",
            )
            token = bind_context(ctx)
            started = time.perf_counter()
            logger = get_logger("aegis.api.http", service=service_name)
            tracer = None
            span = None
            runtime = get_runtime()
            try:
                if runtime is not None and runtime.tracer_provider is not None:
                    from opentelemetry import trace

                    tracer = trace.get_tracer("aegis.api")
                    span = tracer.start_span(
                        f"HTTP {request.method} {_route_group(request.url.path)}"
                    )
                    span.set_attribute("http.method", request.method)
                    span.set_attribute("http.route_group", _route_group(request.url.path))
                    span.set_attribute("aegis.trace_id", ctx.trace_id)
                    if ctx.request_id:
                        span.set_attribute("aegis.request_id", ctx.request_id)

                response = await call_next(request)
                duration_ms = (time.perf_counter() - started) * 1000.0
                status_code = response.status_code
                error = status_code >= 500
                merge_context(
                    duration_ms=duration_ms,
                    outcome=LogOutcomeV1.FAILURE if error else LogOutcomeV1.SUCCESS,
                )
                try:
                    get_metrics().record_api_request(
                        duration_ms=duration_ms,
                        status=str(status_code),
                        method=request.method,
                        route_group=_route_group(request.url.path),
                        error=error,
                    )
                except Exception:  # noqa: BLE001
                    if runtime is not None:
                        runtime.record_exporter_failure()

                logger.info(
                    "HTTP request completed",
                    operation="http.request",
                    outcome="failure" if error else "success",
                    duration_ms=duration_ms,
                    method=request.method,
                    route_group=_route_group(request.url.path),
                    status=status_code,
                )
                for key, value in propagate_headers(get_context_safe(ctx)).items():
                    response.headers[key] = value
                if span is not None:
                    span.set_attribute("http.status_code", status_code)
                    if error:
                        try:
                            from opentelemetry.trace import Status, StatusCode

                            span.set_status(Status(StatusCode.ERROR))
                        except Exception:  # noqa: BLE001
                            pass
                    span.end()
                return response
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000.0
                logger.error(
                    "HTTP request failed",
                    operation="http.request",
                    outcome="failure",
                    duration_ms=duration_ms,
                    error_kind=type(exc).__name__,
                    method=request.method,
                    route_group=_route_group(request.url.path),
                )
                if span is not None:
                    try:
                        from opentelemetry.trace import Status, StatusCode

                        span.set_status(Status(StatusCode.ERROR, str(type(exc).__name__)))
                        span.record_exception(exc)
                    except Exception:  # noqa: BLE001
                        pass
                    span.end()
                raise
            finally:
                clear_context(token)

    return ObservabilityMiddleware


def get_context_safe(fallback: TelemetryContextState) -> TelemetryContextState:
    from aegis_observability.context import get_context

    return get_context() or fallback


def bind_actor_context(
    *,
    actor_id: str,
    actor_role: str | None = None,
    actor_kind: ActorKindV1 = ActorKindV1.USER,
) -> TelemetryContextState:
    """Attach authenticated actor identity safely (no secrets)."""
    return merge_context(
        actor_id=actor_id,
        actor_role=actor_role,
        actor_kind=actor_kind,
    )
