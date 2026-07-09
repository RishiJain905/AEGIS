"""Checksum, archive integrity, and state-diff unit tests."""

from __future__ import annotations

from aegis_contracts import ReplayModeV1
from aegis_contracts.replay import ReplayErrorCode
from aegis_replay.checksum import (
    compute_state_digest,
    deserialize_snapshot_archive,
    serialize_snapshot_archive,
    verify_archive_checksum,
)
from aegis_replay.diff import diff_states
from aegis_replay.errors import ReplayEngineError
from aegis_replay.projectors import ReplayProjector, empty_provenance

from tests.replay.helpers import RUN_ID, sample_history


def _state_at(count: int):
    projector = ReplayProjector(RUN_ID)
    for event in sample_history(count=count):
        projector.apply_event(event)
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=1,
        applied_to=count,
        applied_count=count,
    )
    return projector.to_replay_state(provenance=provenance)


def test_state_digest_stable_for_same_projection() -> None:
    state_a = _state_at(12)
    state_b = _state_at(12)
    assert compute_state_digest(state_a) == compute_state_digest(state_b)
    assert state_a.state_digest == state_b.state_digest


def test_archive_roundtrip_and_checksum_reject() -> None:
    from datetime import UTC, datetime

    from aegis_contracts import ReplaySnapshotV1
    from aegis_contracts.versioning import REPLAY_SNAPSHOT_SCHEMA_VERSION, WORKSPACE_VERSION
    from aegis_replay.versioning import REPLAY_PROJECTOR_VERSION

    state = _state_at(10)
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
    verify_archive_checksum(data=data, expected_checksum=checksum)
    restored = deserialize_snapshot_archive(data)
    assert restored.id == snapshot.id
    assert restored.state_digest == snapshot.state_digest

    tampered = data[:-4] + b"XXXX"
    try:
        verify_archive_checksum(data=tampered, expected_checksum=checksum)
        rejected = False
    except ReplayEngineError as exc:
        rejected = True
        assert exc.code == ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH
    assert rejected


def test_state_diff_detects_changes() -> None:
    early = _state_at(8)
    late = _state_at(16)
    diff = diff_states(early, late)
    assert diff.equivalent is False
    assert len(diff.entries) > 0
    same = diff_states(late, _state_at(16))
    assert same.equivalent is True
