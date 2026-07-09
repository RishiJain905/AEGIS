"""Structured replay engine errors."""

from __future__ import annotations

from aegis_contracts.replay import ReplayErrorCode


class ReplayEngineError(Exception):
    def __init__(
        self,
        code: ReplayErrorCode,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
