"""Deterministic priority event queue."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime

from aegis_contracts.simulation import ScheduledEventV1


@dataclass(order=True, slots=True)
class _QueueEntry:
    sort_key: tuple[datetime, int, int, str]
    event: ScheduledEventV1 = field(compare=False)


class DeterministicEventQueue:
    def __init__(self) -> None:
        self._heap: list[_QueueEntry] = []

    def enqueue(self, event: ScheduledEventV1) -> None:
        sort_key = (
            event.sim_time,
            event.priority,
            event.tie_breaker,
            event.event_id,
        )
        heapq.heappush(self._heap, _QueueEntry(sort_key, event))

    def enqueue_many(self, events: list[ScheduledEventV1]) -> None:
        for event in sorted(
            events,
            key=lambda item: (item.sim_time, item.priority, item.tie_breaker, item.event_id),
        ):
            self.enqueue(event)

    def peek(self) -> ScheduledEventV1 | None:
        if not self._heap:
            return None
        return self._heap[0].event

    def pop(self) -> ScheduledEventV1 | None:
        if not self._heap:
            return None
        return heapq.heappop(self._heap).event

    def is_empty(self) -> bool:
        return not self._heap

    def to_list(self) -> list[ScheduledEventV1]:
        copied = sorted(self._heap, key=lambda entry: entry.sort_key)
        return [entry.event for entry in copied]

    @classmethod
    def from_list(cls, events: list[ScheduledEventV1]) -> DeterministicEventQueue:
        queue = cls()
        queue.enqueue_many(events)
        return queue
