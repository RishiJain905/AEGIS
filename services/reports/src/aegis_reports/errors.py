"""Structured errors for report generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReportErrorCode(StrEnum):
    INCIDENT_NOT_FOUND = "INCIDENT_NOT_FOUND"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    EXPORT_NOT_FOUND = "EXPORT_NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    GROUNDING_FAILED = "GROUNDING_FAILED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ReportError(Exception):
    code: ReportErrorCode
    message: str
    trace_id: str | None = None
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message
