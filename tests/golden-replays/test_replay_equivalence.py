"""Golden live-final vs reconstructed-final equivalence (Phase 25 AC1)."""

from __future__ import annotations

from aegis_contracts import ReplayModeV1
from aegis_replay.diff import diff_states
from aegis_replay.projectors import ReplayProjector, empty_provenance
from tests.replay.helpers import RUN_ID, sample_history


def test_silent_relay_style_history_snapshot_tail_matches_full_replay() -> None:
    history = sample_history(count=20)

    live = ReplayProjector(RUN_ID)
    for event in history:
        live.apply_event(event)
    live_state = live.to_replay_state(
        provenance=empty_provenance(
            run_id=RUN_ID,
            mode=ReplayModeV1.FROM_EVENTS,
            applied_from=1,
            applied_to=20,
            applied_count=20,
        )
    )

    mid = ReplayProjector(RUN_ID)
    for event in history:
        if event.sequence <= 10:
            mid.apply_event(event)
    mid_state = mid.to_replay_state(
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

    assert live_state.state_digest == reconstructed.state_digest
    assert diff_states(live_state, reconstructed).equivalent is True
    assert reconstructed.provenance.mode == ReplayModeV1.FROM_SNAPSHOT_PLUS_EVENTS
