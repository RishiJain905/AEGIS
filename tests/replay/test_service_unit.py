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


def test_resolve_target_sequence_rejects_sequence_past_the_end() -> None:
    """Comparison paths must fail loudly rather than answer for a different sequence."""
    from aegis_contracts.replay import ReplayErrorCode
    from aegis_replay.errors import ReplayEngineError

    service = ReplayService(InMemoryObjectStorage.create())
    events = sample_history(count=12)
    try:
        service._resolve_target_sequence(events, sequence=500, sim_time=None)
    except ReplayEngineError as exc:
        assert exc.code is ReplayErrorCode.REPLAY_VALIDATION_FAILED
        assert exc.details["maxSequence"] == 12
    else:  # pragma: no cover - strict path must raise
        raise AssertionError("sequence past the end was accepted")


def test_resolve_target_sequence_clamps_for_operator_scrubbing() -> None:
    """Scrubbing to End lands on the run's last real state instead of a 400."""
    service = ReplayService(InMemoryObjectStorage.create())
    events = sample_history(count=12)
    target = service._resolve_target_sequence(
        events,
        sequence=500,
        sim_time=None,
        clamp_sequence=True,
    )
    assert target == 12


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


def test_assert_read_only_blocks_event_append() -> None:
    """The replay read-only guard must mechanically fail closed on a live-event append."""
    import asyncio

    from aegis_contracts.replay import ReplayErrorCode
    from aegis_replay.errors import ReplayEngineError

    class _FakeUnitOfWork:
        def __init__(self) -> None:
            self.appended: list[object] = []

        async def append_event(self, envelope: object) -> object:
            self.appended.append(envelope)
            return envelope

    service = ReplayService(InMemoryObjectStorage.create())
    uow = _FakeUnitOfWork()

    # Before arming, appends are permitted (models a normal live command context).
    assert asyncio.run(uow.append_event("live-event")) == "live-event"

    service.assert_read_only(uow)  # type: ignore[arg-type]

    try:
        asyncio.run(uow.append_event("replay-event"))
    except ReplayEngineError as exc:
        assert exc.code is ReplayErrorCode.REPLAY_LIVE_MUTATION_FORBIDDEN
    else:  # pragma: no cover - guard must fail closed
        raise AssertionError("assert_read_only did not block append_event")

    # No second live event slipped through, and re-arming stays idempotent.
    assert uow.appended == ["live-event"]
    service.assert_read_only(uow)  # type: ignore[arg-type]


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
