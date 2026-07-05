"""Agent runtime error types."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AgentRuntimeErrorCode(StrEnum):
    TOOL_UNAUTHORIZED = "TOOL_UNAUTHORIZED"
    TOOL_VALIDATION_FAILED = "TOOL_VALIDATION_FAILED"
    EVIDENCE_NOT_VISIBLE = "EVIDENCE_NOT_VISIBLE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    TASK_CANCELLED = "TASK_CANCELLED"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    INCIDENT_NOT_FOUND = "INCIDENT_NOT_FOUND"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    INTERNAL = "INTERNAL"


class AgentRuntimeError(Exception):
    def __init__(
        self,
        *,
        code: AgentRuntimeErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        self.retryable = retryable
        super().__init__(message)
