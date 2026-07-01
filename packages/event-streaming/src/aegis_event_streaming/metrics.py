"""In-memory streaming metrics for observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class StreamingMetrics:
    outbox_unpublished: int = 0
    outbox_oldest_age_seconds: float | None = None
    publish_latency_ms: float = 0.0
    publishes_total: int = 0
    publish_retries_total: int = 0
    consumer_lag: int = 0
    pending_messages: int = 0
    dlq_count: int = 0
    backfills_total: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def snapshot(self) -> dict[str, float | int | None]:
        with self._lock:
            return {
                "outboxUnpublished": self.outbox_unpublished,
                "outboxOldestAgeSeconds": self.outbox_oldest_age_seconds,
                "publishLatencyMs": self.publish_latency_ms,
                "publishesTotal": self.publishes_total,
                "publishRetriesTotal": self.publish_retries_total,
                "consumerLag": self.consumer_lag,
                "pendingMessages": self.pending_messages,
                "dlqCount": self.dlq_count,
                "backfillsTotal": self.backfills_total,
            }

    def record_publish(self, *, latency_ms: float) -> None:
        with self._lock:
            self.publishes_total += 1
            self.publish_latency_ms = latency_ms

    def record_publish_retry(self) -> None:
        with self._lock:
            self.publish_retries_total += 1

    def update_outbox_stats(self, *, unpublished: int, oldest_age_seconds: float | None) -> None:
        with self._lock:
            self.outbox_unpublished = unpublished
            self.outbox_oldest_age_seconds = oldest_age_seconds

    def update_consumer_stats(self, *, lag: int, pending: int) -> None:
        with self._lock:
            self.consumer_lag = lag
            self.pending_messages = pending

    def update_dlq_count(self, count: int) -> None:
        with self._lock:
            self.dlq_count = count

    def record_backfill(self) -> None:
        with self._lock:
            self.backfills_total += 1


GLOBAL_METRICS = StreamingMetrics()
