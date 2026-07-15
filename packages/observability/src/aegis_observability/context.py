"""Correlation context propagation across process and async boundaries."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import Any

from aegis_contracts.observability import ActorKindV1, LogOutcomeV1
from aegis_contracts.versioning import TELEMETRY_CONTEXT_SCHEMA_VERSION

_TRACEPARENT = "traceparent"
_TRACESTATE = "tracestate"
_REQUEST_ID = "x-request-id"
_CORRELATION_ID = "x-correlation-id"
_AEGIS_RUN_ID = "x-aegis-run-id"
_AEGIS_INCIDENT_ID = "x-aegis-incident-id"


def _new_trace_id() -> str:
    # Domain contracts use trc_ + ULID-like suffix; keep compatible runtime IDs.
    return f"trc_{uuid.uuid4().hex[:26].upper()}"


def _new_span_id() -> str:
    return secrets.token_hex(8)


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:26].upper()}"


@dataclass(frozen=True, slots=True)
class TelemetryContextState:
    """In-process telemetry context (not the durable contract model)."""

    schema_version: int = TELEMETRY_CONTEXT_SCHEMA_VERSION
    trace_id: str = field(default_factory=_new_trace_id)
    span_id: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    run_id: str | None = None
    incident_id: str | None = None
    agent_session_id: str | None = None
    event_sequence: int | None = None
    service: str = "unknown"
    operation: str = "unknown"
    actor_id: str | None = None
    actor_kind: ActorKindV1 | None = None
    actor_role: str | None = None
    outcome: LogOutcomeV1 | None = None
    duration_ms: float | None = None
    baggage: dict[str, str] = field(default_factory=dict)

    def with_updates(self, **kwargs: Any) -> TelemetryContextState:
        return replace(self, **kwargs)

    def to_log_fields(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "correlation_id": self.correlation_id or self.trace_id,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "incident_id": self.incident_id,
            "agent_session_id": self.agent_session_id,
            "event_sequence": self.event_sequence,
            "service": self.service,
            "operation": self.operation,
            "actor_id": self.actor_id,
            "actor_kind": self.actor_kind.value if self.actor_kind else None,
            "actor_role": self.actor_role,
            "outcome": self.outcome.value if self.outcome else None,
            "duration_ms": self.duration_ms,
        }

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "correlationId": self.correlation_id or self.trace_id,
            "requestId": self.request_id,
            "runId": self.run_id,
            "incidentId": self.incident_id,
            "agentSessionId": self.agent_session_id,
            "eventSequence": self.event_sequence,
            "service": self.service,
            "operation": self.operation,
            "actorId": self.actor_id,
            "actorKind": self.actor_kind.value if self.actor_kind else None,
            "actorRole": self.actor_role,
            "outcome": self.outcome.value if self.outcome else None,
            "durationMs": self.duration_ms,
            "baggage": dict(self.baggage),
        }


_CONTEXT: ContextVar[TelemetryContextState | None] = ContextVar(
    "aegis_telemetry_context",
    default=None,
)


def get_context() -> TelemetryContextState | None:
    return _CONTEXT.get()


def bind_context(ctx: TelemetryContextState) -> Token[TelemetryContextState | None]:
    return _CONTEXT.set(ctx)


def clear_context(token: Token[TelemetryContextState | None] | None = None) -> None:
    if token is not None:
        _CONTEXT.reset(token)
    else:
        _CONTEXT.set(None)


def merge_context(**kwargs: Any) -> TelemetryContextState:
    current = get_context()
    if current is None:
        base = TelemetryContextState(
            request_id=_new_request_id(),
            span_id=_new_span_id(),
            correlation_id=kwargs.get("correlation_id") or kwargs.get("trace_id"),
        )
        updated = base.with_updates(**{k: v for k, v in kwargs.items() if v is not None})
        if updated.correlation_id is None:
            updated = updated.with_updates(correlation_id=updated.trace_id)
        bind_context(updated)
        return updated
    updated = current.with_updates(**{k: v for k, v in kwargs.items() if v is not None})
    bind_context(updated)
    return updated


@contextmanager
def use_context(ctx: TelemetryContextState) -> Iterator[TelemetryContextState]:
    token = bind_context(ctx)
    try:
        yield ctx
    finally:
        clear_context(token)


def _parse_traceparent(value: str) -> tuple[str | None, str | None]:
    # W3C: version-trace_id-parent_id-flags (hex). Map hex trace to trc_ domain id when needed.
    parts = value.strip().split("-")
    if len(parts) != 4:
        return None, None
    _version, hex_trace, hex_span, _flags = parts
    if len(hex_trace) != 32 or len(hex_span) != 16:
        return None, None
    # Prefer preserving inbound aegis trc_ via x-correlation-id; synthesize compatible id from hex.
    return f"trc_{hex_trace[:26].upper()}", hex_span


def extract_headers(headers: Mapping[str, str]) -> TelemetryContextState:
    lowered = {k.lower(): v for k, v in headers.items()}
    request_id = lowered.get(_REQUEST_ID) or _new_request_id()
    correlation_id = lowered.get(_CORRELATION_ID)
    run_id = lowered.get(_AEGIS_RUN_ID)
    incident_id = lowered.get(_AEGIS_INCIDENT_ID)
    trace_id: str | None = None
    span_id: str | None = None
    if _TRACEPARENT in lowered:
        trace_id, span_id = _parse_traceparent(lowered[_TRACEPARENT])
    if correlation_id and correlation_id.startswith("trc_") and trace_id is None:
        # Prefer explicit correlation/trace identifiers from AEGIS clients.
        trace_id = correlation_id
    if trace_id is None:
        trace_id = _new_trace_id()
    if correlation_id is None:
        correlation_id = trace_id
    return TelemetryContextState(
        trace_id=trace_id,
        span_id=span_id or _new_span_id(),
        correlation_id=correlation_id,
        request_id=request_id,
        run_id=run_id,
        incident_id=incident_id,
    )


def propagate_headers(ctx: TelemetryContextState | None = None) -> dict[str, str]:
    state = ctx or get_context()
    if state is None:
        state = TelemetryContextState(request_id=_new_request_id(), span_id=_new_span_id())
    # Encode a W3C-compatible traceparent from the domain trace id hex suffix.
    hex_trace = "".join(c for c in state.trace_id if c.isalnum())[-32:].lower().zfill(32)
    hex_span = (state.span_id or _new_span_id()).lower().zfill(16)[-16:]
    headers = {
        _TRACEPARENT: f"00-{hex_trace}-{hex_span}-01",
        _REQUEST_ID: state.request_id or _new_request_id(),
        _CORRELATION_ID: state.correlation_id or state.trace_id,
    }
    if state.run_id:
        headers[_AEGIS_RUN_ID] = state.run_id
    if state.incident_id:
        headers[_AEGIS_INCIDENT_ID] = state.incident_id
    return headers
