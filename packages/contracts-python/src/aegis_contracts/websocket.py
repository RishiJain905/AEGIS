"""WebSocket gateway protocol contracts for Phase 12."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ApiErrorEnvelopeV1, ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import RunId, Sequence, TraceId, UtcTimestamp
from aegis_contracts.realtime import RealtimeMessageEnvelopeV1
from aegis_contracts.versioning import (
    PROTOCOL_VERSION_V1,
    WEBSOCKET_FRAME_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class WebSocketMessageType(StrEnum):
    HELLO = "hello"
    HELLO_ACK = "hello_ack"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PONG = "pong"
    SUBSCRIBED = "subscribed"
    EVENT = "event"
    WARNING = "warning"
    ERROR = "error"
    SNAPSHOT_REQUIRED = "snapshot_required"
    PING = "ping"
    RESYNC_COMPLETE = "resync_complete"
    RUN_TERMINATED = "run_terminated"


class WebSocketErrorCode(StrEnum):
    WS_UNAUTHORIZED = "WS_UNAUTHORIZED"
    WS_FORBIDDEN = "WS_FORBIDDEN"
    WS_INVALID_MESSAGE = "WS_INVALID_MESSAGE"
    WS_MESSAGE_TOO_LARGE = "WS_MESSAGE_TOO_LARGE"
    WS_UNSUPPORTED_PROTOCOL = "WS_UNSUPPORTED_PROTOCOL"
    WS_UNKNOWN_RUN = "WS_UNKNOWN_RUN"
    WS_SEQUENCE_GAP = "WS_SEQUENCE_GAP"
    WS_QUEUE_OVERFLOW = "WS_QUEUE_OVERFLOW"
    WS_IDLE_TIMEOUT = "WS_IDLE_TIMEOUT"
    WS_CONNECTION_LIMIT = "WS_CONNECTION_LIMIT"


class WebSocketDeliveryMode(StrEnum):
    STREAM = "stream"
    BACKFILL = "backfill"
    SNAPSHOT_REQUIRED = "snapshot_required"


class WebSocketHelloPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_version: int = Field(alias="protocolVersion", ge=1)
    auth_token: str | None = Field(default=None, alias="authToken", max_length=4096)


class WebSocketHelloAckPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_version: int = Field(alias="protocolVersion", ge=1)
    connection_id: str = Field(alias="connectionId", min_length=1, max_length=128)
    principal_id: str = Field(alias="principalId", min_length=1, max_length=256)


class WebSocketSubscribePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    channel: str = Field(min_length=1, max_length=128)
    last_applied_sequence: Sequence = Field(alias="lastAppliedSequence", ge=0)


class WebSocketUnsubscribePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    channel: str = Field(min_length=1, max_length=128)


class WebSocketPongPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    server_time: UtcTimestamp = Field(alias="serverTime")


class WebSocketSubscribedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    channel: str = Field(min_length=1, max_length=128)
    last_applied_sequence: Sequence = Field(alias="lastAppliedSequence", ge=0)
    delivery_mode: WebSocketDeliveryMode = Field(alias="deliveryMode")


class WebSocketEventPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    envelope: RealtimeMessageEnvelopeV1


class WebSocketWarningPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2048)
    run_id: RunId | None = Field(default=None, alias="runId")
    details: dict[str, Any] = Field(default_factory=dict)


class WebSocketErrorPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    error: ApiErrorEnvelopeV1


class WebSocketSnapshotRequiredPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    reason: WebSocketErrorCode
    from_sequence: Sequence = Field(alias="fromSequence", ge=0)
    to_sequence: Sequence | None = Field(default=None, alias="toSequence", ge=0)


class WebSocketPingPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    server_time: UtcTimestamp = Field(alias="serverTime")


class WebSocketResyncCompletePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    from_sequence: Sequence = Field(alias="fromSequence", ge=0)
    to_sequence: Sequence = Field(alias="toSequence", ge=0)
    events_delivered: int = Field(alias="eventsDelivered", ge=0)


class WebSocketRunTerminatedPayloadV1(BaseModel):
    """Server → client: the subscribed run has ended; no further events will be delivered."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId")
    status: str = Field(min_length=1, max_length=64)


_PAYLOAD_MODEL_BY_TYPE: dict[WebSocketMessageType, type[BaseModel]] = {
    WebSocketMessageType.HELLO: WebSocketHelloPayloadV1,
    WebSocketMessageType.HELLO_ACK: WebSocketHelloAckPayloadV1,
    WebSocketMessageType.SUBSCRIBE: WebSocketSubscribePayloadV1,
    WebSocketMessageType.UNSUBSCRIBE: WebSocketUnsubscribePayloadV1,
    WebSocketMessageType.PONG: WebSocketPongPayloadV1,
    WebSocketMessageType.SUBSCRIBED: WebSocketSubscribedPayloadV1,
    WebSocketMessageType.EVENT: WebSocketEventPayloadV1,
    WebSocketMessageType.WARNING: WebSocketWarningPayloadV1,
    WebSocketMessageType.ERROR: WebSocketErrorPayloadV1,
    WebSocketMessageType.SNAPSHOT_REQUIRED: WebSocketSnapshotRequiredPayloadV1,
    WebSocketMessageType.PING: WebSocketPingPayloadV1,
    WebSocketMessageType.RESYNC_COMPLETE: WebSocketResyncCompletePayloadV1,
    WebSocketMessageType.RUN_TERMINATED: WebSocketRunTerminatedPayloadV1,
}


class WebSocketFrameV1(BaseModel):
    """Versioned WebSocket wire frame."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    protocol_version: int = Field(alias="protocolVersion", ge=1)
    message_type: WebSocketMessageType = Field(alias="messageType")
    trace_id: TraceId = Field(alias="traceId")
    sent_at: UtcTimestamp = Field(alias="sentAt")
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_frame(self) -> WebSocketFrameV1:
        assert_supported_schema_version("websocket_frame", self.schema_version)
        if self.schema_version != WEBSOCKET_FRAME_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported websocket frame schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.protocol_version != PROTOCOL_VERSION_V1:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported websocket protocol version: {self.protocol_version}",
                details={"protocolVersion": self.protocol_version},
            )
        payload_model = _PAYLOAD_MODEL_BY_TYPE.get(self.message_type)
        if payload_model is None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message=f"Unknown websocket message type: {self.message_type}",
                details={"messageType": self.message_type},
            )
        payload_model.model_validate(self.payload)
        return self

    def typed_payload(self) -> BaseModel:
        payload_model = _PAYLOAD_MODEL_BY_TYPE[self.message_type]
        return payload_model.model_validate(self.payload)


def build_websocket_frame(
    *,
    message_type: WebSocketMessageType,
    trace_id: str,
    sent_at: UtcTimestamp,
    payload: BaseModel,
) -> WebSocketFrameV1:
    return WebSocketFrameV1(
        schema_version=WEBSOCKET_FRAME_SCHEMA_VERSION,
        protocol_version=PROTOCOL_VERSION_V1,
        message_type=message_type,
        trace_id=trace_id,
        sent_at=sent_at,
        payload=payload.model_dump(mode="json", by_alias=True),
    )
