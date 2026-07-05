"""JSON Schema validation for tool inputs and outputs."""

from __future__ import annotations

from typing import Any

import jsonschema
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode


def validate_payload(
    payload: dict[str, Any],
    schema: dict[str, Any],
    *,
    label: str,
    trace_id: str | None = None,
) -> None:
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Invalid {label}: {exc.message}",
            details={"label": label, "path": list(exc.path)},
            trace_id=trace_id,
        ) from exc
