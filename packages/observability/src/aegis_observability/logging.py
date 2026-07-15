"""Structured JSON logging with approved correlation fields."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from aegis_contracts.observability import LogOutcomeV1
from aegis_contracts.versioning import STRUCTURED_LOG_RECORD_SCHEMA_VERSION

from aegis_observability.context import get_context
from aegis_observability.redaction import redact_mapping, redact_string

_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class StructuredLogger:
    def __init__(self, name: str, *, service: str, json_logs: bool = True) -> None:
        self._logger = logging.getLogger(name)
        self._service = service
        self._json_logs = json_logs

    def _emit(
        self,
        level: str,
        message: str,
        *,
        operation: str | None = None,
        outcome: LogOutcomeV1 | str | None = None,
        duration_ms: float | None = None,
        error_kind: str | None = None,
        **attributes: Any,
    ) -> None:
        ctx = get_context()
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        safe_attrs = redact_mapping(dict(attributes))
        outcome_value: str | None = (
            outcome.value if isinstance(outcome, LogOutcomeV1) else outcome
        )
        record = {
            "schemaVersion": STRUCTURED_LOG_RECORD_SCHEMA_VERSION,
            "timestamp": ts,
            "level": level,
            "message": redact_string(message),
            "traceId": ctx.trace_id if ctx else None,
            "spanId": ctx.span_id if ctx else None,
            "correlationId": (ctx.correlation_id or ctx.trace_id) if ctx else None,
            "requestId": ctx.request_id if ctx else None,
            "runId": ctx.run_id if ctx else None,
            "incidentId": ctx.incident_id if ctx else None,
            "agentSessionId": ctx.agent_session_id if ctx else None,
            "eventSequence": ctx.event_sequence if ctx else None,
            "service": (ctx.service if ctx and ctx.service != "unknown" else self._service),
            "operation": operation
            or (ctx.operation if ctx and ctx.operation != "unknown" else "unknown"),
            "actorId": ctx.actor_id if ctx else None,
            "actorKind": ctx.actor_kind.value if ctx and ctx.actor_kind else None,
            "outcome": outcome_value,
            "durationMs": (
                duration_ms if duration_ms is not None else (ctx.duration_ms if ctx else None)
            ),
            "errorKind": error_kind,
            "attributes": safe_attrs,
        }
        text = json.dumps(record, default=str, separators=(",", ":")) if self._json_logs else (
            f"{ts} {level.upper()} {record['service']} {record['operation']} "
            f"trace={record['traceId']} {message}"
        )
        self._logger.log(_LEVEL_MAP.get(level, logging.INFO), text)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit("debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._emit("warn", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._emit("error", message, **kwargs)


_loggers: dict[str, StructuredLogger] = {}


def configure_root_logging(*, level: str = "info", json_logs: bool = True) -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
    root.setLevel(_LEVEL_MAP.get(level.lower(), logging.INFO))
    # Silence noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str, *, service: str = "aegis", json_logs: bool = True) -> StructuredLogger:
    key = f"{service}:{name}:{json_logs}"
    if key not in _loggers:
        _loggers[key] = StructuredLogger(name, service=service, json_logs=json_logs)
    return _loggers[key]
