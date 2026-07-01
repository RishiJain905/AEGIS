"""Streaming configuration with environment defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamingConfig:
    stream_maxlen: int
    outbox_claim_ttl_seconds: int
    outbox_batch_size: int
    outbox_poll_interval_seconds: float
    outbox_retry_delay_seconds: int
    consumer_max_attempts: int
    consumer_block_ms: int
    consumer_pending_idle_ms: int

    @classmethod
    def from_env(cls) -> StreamingConfig:
        return cls(
            stream_maxlen=int(os.environ.get("AEGIS_STREAM_MAXLEN", "100000")),
            outbox_claim_ttl_seconds=int(os.environ.get("AEGIS_OUTBOX_CLAIM_TTL_SECONDS", "60")),
            outbox_batch_size=int(os.environ.get("AEGIS_OUTBOX_BATCH_SIZE", "50")),
            outbox_poll_interval_seconds=float(
                os.environ.get("AEGIS_OUTBOX_POLL_INTERVAL_SECONDS", "1.0")
            ),
            outbox_retry_delay_seconds=int(os.environ.get("AEGIS_OUTBOX_RETRY_DELAY_SECONDS", "5")),
            consumer_max_attempts=int(os.environ.get("AEGIS_CONSUMER_MAX_ATTEMPTS", "3")),
            consumer_block_ms=int(os.environ.get("AEGIS_CONSUMER_BLOCK_MS", "1000")),
            consumer_pending_idle_ms=int(os.environ.get("AEGIS_CONSUMER_PENDING_IDLE_MS", "1000")),
        )
