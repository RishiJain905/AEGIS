"""Acceptance-criterion tests mapped to Phase 25 §18."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import ReplayModeV1, ReplaySnapshotV1, SnapshotTriggerReasonV1
from aegis_contracts.replay import ReplayErrorCode
from aegis_contracts.versioning import REPLAY_SNAPSHOT_SCHEMA_VERSION, WORKSPACE_VERSION
from aegis_persistence.object_storage import InMemoryObjectStorage
from aegis_replay.checksum import serialize_snapshot_archive, verify_archive_checksum
from aegis_replay.diff import diff_states
from aegis_replay.errors import ReplayEngineError
from aegis_replay.projectors import ReplayProjector, empty_provenance
from aegis_replay.service import ReplayService
from aegis_replay.versioning import REPLAY_PROJECTOR_VERSION

from tests.replay.helpers import RUN_ID, make_event, sample_history


def _project(count: int, *, mode: ReplayModeV1 = ReplayModeV1.FROM_EVENTS):
    projector = ReplayProjector(RUN_ID)
    history = sample_history(count=count)
    for event in history:
        projector.apply_event(event)
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=mode,
        applied_from=1,
        applied_to=count,
        applied_count=count,
    )
    return projector.to_replay_state(provenance=provenance), history


def test_ac1_golden_final_replay_equals_live_final_projection() -> None:
    """AC1: event-only reconstruction equals snapshot+tail reconstruction."""
    live, history = _project(20)
    # Build intermediate snapshot state at sequence 10.
    mid_projector = ReplayProjector(RUN_ID)
    for event in history:
        if event.sequence <= 10:
            mid_projector.apply_event(event)
    mid_state = mid_projector.to_replay_state(
        provenance=empty_provenance(
            run_id=RUN_ID,
            mode=ReplayModeV1.FROM_EVENTS,
            applied_from=1,
            applied_to=10,
            applied_count=10,
            snapshot_id="rps_01ARZ3NDEKTSV4RRFFQ69G5FC0",
            snapshot_sequence=10,
        )
    )
    # Reconstruct from snapshot + later events.
    resumed = ReplayProjector.from_replay_state(mid_state)
    for event in history:
        if event.sequence > 10:
            resumed.apply_event(event)
    reconstructed = resumed.to_replay_state(
        provenance=empty_provenance(
            run_id=RUN_ID,
            mode=ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS,
            applied_from=11,
            applied_to=20,
            applied_count=10,
            snapshot_id="rps_01ARZ3NDEKTSV4RRFFQ69G5FC0",
            snapshot_sequence=10,
        )
    )
    assert live.state_digest == reconstructed.state_digest
    assert diff_states(live, reconstructed).equivalent is True


def test_ac2_historical_replay_performs_zero_external_model_calls() -> None:
    """AC2: projector forbids model calls during historical replay."""
    projector = ReplayProjector(RUN_ID)
    with pytest.raises(ReplayEngineError) as exc_info:
        projector.forbid_model_calls()
    assert exc_info.value.code == ReplayErrorCode.REPLAY_LIVE_MUTATION_FORBIDDEN
    assert projector.state.model_call_attempts == 1


def test_ac3_corrupt_snapshot_checksum_rejected_safely() -> None:
    """AC3: corrupt archives fail closed on checksum mismatch."""
    state, _history = _project(12)
    snapshot = ReplaySnapshotV1(
        schema_version=REPLAY_SNAPSHOT_SCHEMA_VERSION,
        id="rps_01ARZ3NDEKTSV4RRFFQ69G5FC0",  # type: ignore[arg-type]
        run_id=RUN_ID,  # type: ignore[arg-type]
        sequence=state.cursor.sequence,
        sim_time=state.cursor.sim_time or datetime.now(tz=UTC),
        scenario_version_id="scenario-version:v1.0.0-synthetic",
        engine_version="0.0.0-phase09",
        projector_version=REPLAY_PROJECTOR_VERSION,
        workspace_version=WORKSPACE_VERSION,
        event_range_from=0,
        event_range_to=state.cursor.sequence,
        state=state,
        state_digest=state.state_digest,
        created_at=datetime.now(tz=UTC),
    )
    data, checksum = serialize_snapshot_archive(snapshot)
    storage = InMemoryObjectStorage.create()
    key = "snapshots/demo/corrupt.json.gz"
    storage.put_bytes(object_key=key, data=data, content_type="application/gzip")
    tampered = storage.get_bytes(object_key=key)[:-6] + b"TAMPER"
    with pytest.raises(ReplayEngineError) as exc_info:
        verify_archive_checksum(data=tampered, expected_checksum=checksum)
    assert exc_info.value.code == ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH


def test_ac4_every_replay_result_exposes_provenance_and_event_range() -> None:
    """AC4: provenance and applied event range always present."""
    state, _history = _project(15)
    assert state.provenance.run_id == RUN_ID
    assert state.provenance.mode in {
        ReplayModeV1.FROM_EVENTS,
        ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS,
    }
    assert state.provenance.applied_to_sequence >= state.provenance.applied_from_sequence
    assert state.provenance.applied_event_count == 15
    assert state.provenance.reconstructed_at is not None


def test_sequence_gap_detected() -> None:
    service = ReplayService(InMemoryObjectStorage.create())
    events = [
        make_event(
            sequence=1,
            event_type="sim.run.started",
            payload={
                "schemaVersion": 1,
                "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
                "seed": 1,
            },
            event_index=1,
        ),
        make_event(
            sequence=3,
            event_type="sim.run.paused",
            payload={"schemaVersion": 1},
            event_index=3,
        ),
    ]
    with pytest.raises(ReplayEngineError) as exc_info:
        service._assert_sequence_contiguous(events, up_to=3)
    assert exc_info.value.code == ReplayErrorCode.REPLAY_SEQUENCE_GAP


def test_trigger_reason_enum_covers_cadence_and_explicit() -> None:
    assert SnapshotTriggerReasonV1.SEQUENCE_INTERVAL.value == "sequence_interval"
    assert SnapshotTriggerReasonV1.EXPLICIT_REQUEST.value == "explicit_request"
