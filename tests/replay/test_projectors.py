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


def test_agent_session_events_project_without_run_id_in_payload() -> None:
    """Persisted ``agent.session.*`` payloads carry no ``runId``/``incidentId``.

    The run is authoritative on the envelope, so reconstruction must read it from
    there rather than expecting the payload to repeat it. Historical runs recorded
    before this was noticed must keep replaying.
    """
    projector = ReplayProjector(RUN_ID)
    session_id = "agent-session:ags_2wbx78zte6y5bgnay0z3xzwd"
    projector.apply_event(
        make_event(
            sequence=1,
            event_type="agent.session.started",
            payload={
                "schemaVersion": 1,
                "sessionId": session_id,
                "role": "WATCHTOWER",
            },
            subject_id=session_id,
            event_index=1,
        )
    )
    projector.apply_event(
        make_event(
            sequence=2,
            event_type="agent.session.state_changed",
            payload={
                "schemaVersion": 1,
                "sessionId": session_id,
                "fromState": "gathering",
                "toState": "hypothesizing",
                "reason": "model_step_received",
                "taskId": "atk_ST85WYZZ10Z17V8CEH0BA25WNB",
            },
            subject_id=session_id,
            event_index=2,
        )
    )

    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=1,
        applied_to=2,
        applied_count=2,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert len(state.agent_sessions) == 1
    session = state.agent_sessions[0]
    assert session.id == session_id
    assert session.run_id == RUN_ID
    # Run-scoped copilot threads have no incident (ADR 0035) — do not invent one.
    assert session.incident_id is None
    assert session.role.value == "WATCHTOWER"
    assert session.state.value == "hypothesizing"


def test_alert_created_projects_evidence_despite_carrying_its_own_alert_id() -> None:
    """A real ``alert.created`` payload leads with ``id: alert:...`` and has no summary."""
    projector = ReplayProjector(RUN_ID)
    projector.apply_event(
        make_event(
            sequence=13,
            event_type="alert.created",
            payload={
                "schemaVersion": 1,
                "id": "alert:det-83b4c12208df6a15249b",
                "runId": RUN_ID,
                "title": "Unseen source activity detected",
                "assetId": "asset:svc-comms-gateway",
                "severity": "medium",
            },
            subject_id="asset:svc-comms-gateway",
            event_index=13,
        )
    )
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=13,
        applied_to=13,
        applied_count=1,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert len(state.evidence) == 1
    evidence = state.evidence[0]
    assert evidence.id.startswith("evidence:")
    assert evidence.summary == "Unseen source activity detected"
    assert evidence.asset_id == "asset:svc-comms-gateway"


def test_agent_session_state_change_creates_session_when_start_was_pruned() -> None:
    """A state change without a preceding start still lands in the reconstructed state."""
    projector = ReplayProjector(RUN_ID)
    session_id = "agent-session:ags_y7v8djhnda7jzmhd9kgegd1q"
    projector.apply_event(
        make_event(
            sequence=4,
            event_type="agent.session.state_changed",
            payload={
                "schemaVersion": 1,
                "sessionId": session_id,
                "fromState": "queued",
                "toState": "gathering",
                "reason": "task_started",
            },
            subject_id=session_id,
            event_index=4,
        )
    )
    provenance = empty_provenance(
        run_id=RUN_ID,
        mode=ReplayModeV1.FROM_EVENTS,
        applied_from=4,
        applied_to=4,
        applied_count=1,
    )
    state = projector.to_replay_state(provenance=provenance)
    assert len(state.agent_sessions) == 1
    assert state.agent_sessions[0].run_id == RUN_ID
    assert state.agent_sessions[0].state.value == "gathering"


def _status_event(sequence: int, asset_id: str, status: str):
    return make_event(
        sequence=sequence,
        event_type="sim.asset.status_changed",
        subject_id=asset_id,
        payload={"schemaVersion": 1, "assetId": asset_id, "status": status},
    )


def test_replay_composes_posture_and_controls_from_a_legacy_event_stream() -> None:
    """Replay must not let a control overwrite the compromise it was answering.

    The stream carries one applied value per event — the shape every persisted run has,
    including runs recorded before posture and controls were split — so replaying an
    observation over a compromise is the exact reconstruction of the defect. The node has
    to come back compromised *and* under observation.
    """
    asset_id = "asset:svc-api-gateway"
    projector = ReplayProjector(RUN_ID)
    projector.apply_event(_status_event(1, asset_id, "compromised"))
    projector.apply_event(_status_event(2, asset_id, "observed"))

    node = projector.state.graph_nodes[asset_id]
    assert node.status.value == "compromised"
    assert node.applied_controls == ["observed"]

    # Isolating on top reads as contained, and the compromise underneath survives it.
    projector.apply_event(_status_event(3, asset_id, "isolated"))
    node = projector.state.graph_nodes[asset_id]
    assert node.status.value == "contained"
    assert node.applied_controls == ["observed", "isolated"]
    assert projector.state.asset_postures[asset_id] == "compromised"
