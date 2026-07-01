"""Realtime streaming and delivery contracts for Phase 11."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.primitives import EventId, RunId, Sequence, UtcTimestamp
from aegis_contracts.versioning import (
    BACKFILL_REQUEST_SCHEMA_VERSION,
    BACKFILL_RESULT_SCHEMA_VERSION,
    CONSUMER_CURSOR_SCHEMA_VERSION,
    DEAD_LETTER_RECORD_SCHEMA_VERSION,
    REALTIME_MESSAGE_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class StreamingErrorCode(StrEnum):
    STREAM_GAP_DETECTED = "STREAM_GAP_DETECTED"
    STREAM_DUPLICATE = "STREAM_DUPLICATE"
    STREAM_PUBLISH_FAILED = "STREAM_PUBLISH_FAILED"
    STREAM_CONSUMER_UNAVAILABLE = "STREAM_CONSUMER_UNAVAILABLE"
    STREAM_POISON_MESSAGE = "STREAM_POISON_MESSAGE"
    STREAM_BACKFILL_FAILED = "STREAM_BACKFILL_FAILED"


class RealtimeMessageEnvelopeV1(BaseModel):
    """Wire envelope for Redis Streams delivery of domain events."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    channel: str = Field(min_length=1, max_length=128)
    stream_message_id: str | None = Field(default=None, alias="streamMessageId")
    published_at: UtcTimestamp = Field(alias="publishedAt")
    event: DomainEventEnvelopeV1

    @model_validator(mode="after")
    def validate_schema_version(self) -> RealtimeMessageEnvelopeV1:
        assert_supported_schema_version("realtime_message", self.schema_version)
        if self.schema_version != REALTIME_MESSAGE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported realtime message schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ConsumerCursorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    consumer_group: str = Field(alias="consumerGroup", min_length=1, max_length=128)
    consumer_name: str = Field(alias="consumerName", min_length=1, max_length=128)
    stream_key: str = Field(alias="streamKey", min_length=1, max_length=256)
    last_event_id: EventId = Field(alias="lastEventId")
    last_run_id: RunId = Field(alias="lastRunId")
    last_sequence: Sequence = Field(alias="lastSequence", ge=0)
    updated_at: UtcTimestamp = Field(alias="updatedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ConsumerCursorV1:
        assert_supported_schema_version("consumer_cursor", self.schema_version)
        if self.schema_version != CONSUMER_CURSOR_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported consumer cursor schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class DeadLetterRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    event_id: EventId = Field(alias="eventId")
    run_id: RunId = Field(alias="runId")
    sequence: Sequence = Field(ge=0)
    consumer_id: str = Field(alias="consumerId", min_length=1, max_length=256)
    stream_key: str = Field(alias="streamKey", min_length=1, max_length=256)
    stream_message_id: str = Field(alias="streamMessageId", min_length=1, max_length=128)
    error_code: str = Field(alias="errorCode", min_length=1, max_length=128)
    error_message: str = Field(alias="errorMessage", min_length=1, max_length=2048)
    attempt_count: int = Field(alias="attemptCount", ge=1)
    original_envelope: dict[str, Any] = Field(alias="originalEnvelope")
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> DeadLetterRecordV1:
        assert_supported_schema_version("dead_letter_record", self.schema_version)
        if self.schema_version != DEAD_LETTER_RECORD_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported dead letter record schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class BackfillRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId | None = Field(default=None, alias="runId")
    from_sequence: int | None = Field(default=None, alias="fromSequence", ge=0)
    to_sequence: int | None = Field(default=None, alias="toSequence", ge=0)
    stream_key: str | None = Field(default=None, alias="streamKey", max_length=256)
    force: bool = False

    @model_validator(mode="after")
    def validate_schema_version(self) -> BackfillRequestV1:
        assert_supported_schema_version("backfill_request", self.schema_version)
        if self.schema_version != BACKFILL_REQUEST_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported backfill request schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class BackfillResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId | None = Field(default=None, alias="runId")
    events_scanned: int = Field(alias="eventsScanned", ge=0)
    events_published: int = Field(alias="eventsPublished", ge=0)
    events_skipped: int = Field(alias="eventsSkipped", ge=0)
    completed_at: UtcTimestamp = Field(alias="completedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> BackfillResultV1:
        assert_supported_schema_version("backfill_result", self.schema_version)
        if self.schema_version != BACKFILL_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported backfill result schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
