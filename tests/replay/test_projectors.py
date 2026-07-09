"""Unit tests for deterministic replay projectors."""

from __future__ import annotations

from aegis_contracts import ReplayModeV1
from aegis_contracts.entities import ProposalStatus
from aegis_replay.projectors import ReplayProjector, empty_provenance

from tests.replay.helpers import RUN_ID, make_event, sample_history


def test_projector_applies_run_graph_incident_and_approvals() -> None:
    projector = ReplayProjector(RUN_ID)
    for event in sample_history(count=20):
        projector.apply_event(event)

    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=1,
        applied_to=20,
        applied_count=20,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert state.run is not None
    assert state.run.status == "running"
    assert state.graph is not None
    assert any(node.id == "asset:svc-api-gateway" for node in state.graph.nodes)
    assert any(inc.id == "incident:inc_synthetic_001" for inc in state.incidents)
    assert any(ev.id == "evidence:evd_synthetic_001" for ev in state.evidence)
    assert any(score.asset_id == "asset:svc-api-gateway" for score in state.risk_scores)
    assert len(state.proposals) == 1
    assert state.proposals[0].status == ProposalStatus.EXECUTED
    assert len(state.approvals) == 1
    assert len(state.executed_actions) == 1
    assert len(state.reports) == 1
    assert state.state_digest.startswith("sha256:")
    assert state.provenance.applied_event_count == 20


def test_duplicate_events_do_not_duplicate_state() -> None:
    projector = ReplayProjector(RUN_ID)
    history = sample_history(count=10)
    for event in history:
        projector.apply_event(event)
    # Re-apply same events (idempotency by eventId).
    for event in history:
        projector.apply_event(event)
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=1,
        applied_to=10,
        applied_count=10,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert len(state.incidents) == 1
    assert len(state.evidence) == 1
    assert len(projector.state.applied_event_ids) == 10


def test_forbid_model_calls_raises() -> None:
    from aegis_contracts.replay import ReplayErrorCode
    from aegis_replay.errors import ReplayEngineError

    projector = ReplayProjector(RUN_ID)
    try:
        projector.forbid_model_calls()
        raised = False
    except ReplayEngineError as exc:
        raised = True
        assert exc.code == ReplayErrorCode.REPLAY_LIVE_MUTATION_FORBIDDEN
    assert raised


def test_cursor_tracks_last_sequence_and_sim_time() -> None:
    projector = ReplayProjector(RUN_ID)
    event = make_event(
        sequence=7,
        event_type="sim.run.started",
        payload={
            "schemaVersion": 1,
            "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
            "seed": 1,
        },
        event_index=7,
    )
    projector.apply_event(event)
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=7,
        applied_to=7,
        applied_count=1,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert state.cursor.sequence == 7
    assert state.cursor.sim_time == event.sim_time
