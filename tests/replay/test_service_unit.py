"""Unit tests for ReplayService helpers that do not require PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_persistence.object_storage import InMemoryObjectStorage
from aegis_replay.service import ReplayService

from tests.replay.helpers import BASE_TIME, RUN_ID, make_event, sample_history


def test_resolve_target_sequence_by_sim_time() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    events = sample_history(count=10)
    target = service._resolve_target_sequence(
        events,
        sequence=None,
        sim_time=BASE_TIME + timedelta(seconds=5),
    )
    assert target == 5


def test_resolve_target_sequence_defaults_to_latest() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    events = sample_history(count=12)
    assert service._resolve_target_sequence(events, sequence=None, sim_time=None) == 12


def test_build_cursor() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    cursor = service.build_cursor(
        run_id=RUN_ID,
        sequence=9,
        sim_time=datetime(2026, 1, 1, 18, 0, 9, tzinfo=UTC),
        incident_id="incident:inc_synthetic_001",
    )
    assert cursor.sequence == 9
    assert cursor.incident_id == "incident:inc_synthetic_001"


def test_assert_read_only_is_noop() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    service.assert_read_only()


def test_contiguous_history_passes() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    events = [
        make_event(
            sequence=i,
            event_type="sim.run.started" if i == 1 else "sim.run.paused",
            payload={
                "schemaVersion": 1,
                "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
                "seed": 1,
            }
            if i == 1
            else {"schemaVersion": 1},
            event_index=i,
        )
        for i in range(1, 6)
    ]
    service._assert_sequence_contiguous(events, up_to=5)
