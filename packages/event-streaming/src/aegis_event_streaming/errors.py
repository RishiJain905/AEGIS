"""Streaming error types."""

from __future__ import annotations

from typing import Any

from aegis_contracts import StreamingErrorCode


class StreamingError(Exception):
    def __init__(
        self,
        *,
        code: StreamingErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
