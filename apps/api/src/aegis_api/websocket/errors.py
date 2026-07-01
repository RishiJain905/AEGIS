"""Gateway error types mapped to WebSocket error frames."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import (
    ApiErrorEnvelopeV1,
    WebSocketErrorCode,
    WebSocketMessageType,
    build_websocket_frame,
)
from aegis_contracts.versioning import API_ERROR_SCHEMA_VERSION
from aegis_contracts.websocket import WebSocketErrorPayloadV1, WebSocketFrameV1


class GatewayError(Exception):
    def __init__(
        self,
        *,
        code: WebSocketErrorCode,
        message: str,
        details: dict[str, object] | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        super().__init__(message)

    def to_frame(self, *, trace_id: str) -> WebSocketFrameV1:
        return build_websocket_frame(
            message_type=WebSocketMessageType.ERROR,
            trace_id=trace_id,
            sent_at=datetime.now(UTC),
            payload=WebSocketErrorPayloadV1(
                error=ApiErrorEnvelopeV1(
                    schema_version=API_ERROR_SCHEMA_VERSION,
                    code=self.code.value,
                    message=self.message,
                    details=self.details,
                    trace_id=self.trace_id or trace_id,
                )
            ),
        )
