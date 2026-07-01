"""Unit tests for deterministic simulation primitives."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts.simulation import ScheduledEventSourceType, ScheduledEventV1
from aegis_contracts.versioning import SCHEDULED_EVENT_SCHEMA_VERSION
from aegis_simulation_domain.clock import VirtualClock
from aegis_simulation_domain.event_queue import DeterministicEventQueue
from aegis_simulation_domain.random_streams import SeededRandomStreams


def _scheduled(event_id: str, sim_time: str, priority: int, tie_breaker: int) -> ScheduledEventV1:
    return ScheduledEventV1(
        schema_version=SCHEDULED_EVENT_SCHEMA_VERSION,
        event_id=event_id,
        sim_time=datetime.fromisoformat(sim_time.replace("Z", "+00:00")),
        priority=priority,
        tie_breaker=tie_breaker,
        source_type=ScheduledEventSourceType.SCHEDULED,
        plugin_id="telemetry.auth_attempt",
        config={},
        target_asset_id="asset:svc-auth-service",
    )


def test_virtual_clock_advances_forward_only() -> None:
    clock = VirtualClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance_to(datetime(2026, 1, 1, 0, 10, tzinfo=UTC))
    assert clock.sim_time == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    with pytest.raises(ValueError):
        clock.advance_to(datetime(2026, 1, 1, 0, 5, tzinfo=UTC))


def test_event_queue_orders_by_sim_time_priority_tie_breaker() -> None:
    queue = DeterministicEventQueue()
    queue.enqueue_many(
        [
            _scheduled("b", "2026-01-01T00:10:00.000Z", 1, 1),
            _scheduled("a", "2026-01-01T00:10:00.000Z", 1, 0),
            _scheduled("c", "2026-01-01T00:05:00.000Z", 1, 0),
        ]
    )
    assert [queue.pop().event_id for _ in range(3)] == ["c", "a", "b"]


def test_seeded_random_streams_are_deterministic() -> None:
    first = SeededRandomStreams(42)
    second = SeededRandomStreams(42)
    assert first.stream("telemetry").random() == second.stream("telemetry").random()
    assert first.stream("telemetry").random() == second.stream("telemetry").random()


def test_different_seeds_produce_different_random_values() -> None:
    a = SeededRandomStreams(42).stream("telemetry").random()
    b = SeededRandomStreams(99).stream("telemetry").random()
    assert a != b
