"""Ghost branch engine — offline determinism, isolation and enumeration tests.

These build a real-run simulation event stream in memory (a full run with one injected
operator containment) and drive the ghost engine's pure ``compute_ghost`` path — no DB, no
network — mirroring the golden-replay determinism test idiom.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import (
    ActorRef,
    ActorType,
    GhostBranchRequestV1,
    SimulationCommandType,
    SimulationCommandV1,
)
from aegis_contracts.ghost import GhostBranchModeV1
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    GHOST_BRANCH_REQUEST_SCHEMA_VERSION,
    SIMULATION_COMMAND_SCHEMA_VERSION,
)
from aegis_simulation.ghost_engine import GhostBranchEngine, GhostBranchError
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SimulationRuntime

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_VERSION = "scenario-version:1.0.0"
SILENT_RELAY = REPO_ROOT / "scenarios" / "operation-silent-relay"
SEED = 1000
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _engine() -> GhostBranchEngine:
    return GhostBranchEngine(workspace_root=REPO_ROOT)


def _new_runtime() -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(SILENT_RELAY)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest, seed=SEED, scenario_version_id=SCENARIO_VERSION, run_id=RUN_ID
    )
    runtime.start()
    return runtime


def _isolate_command(runtime: SimulationRuntime, asset_id: str) -> SimulationCommandV1:
    return SimulationCommandV1(
        schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
        command_id=f"op-isolate-{asset_id}-{runtime.world.next_sequence}",
        command_type=SimulationCommandType.EXECUTE,
        run_id=runtime.run_id,
        actor=ActorRef(type=ActorType.OPERATOR, id="asset:operator-console"),
        authorization_token="test-operator-token",
        payload={
            "pluginId": "effect.set_asset_status",
            "targetAssetId": asset_id,
            "config": {"assetId": asset_id, "status": "isolated"},
        },
    )


def _bystander_asset() -> tuple[str, str]:
    """Return (asset_id, initial_status) for an asset the scenario never touches."""
    manifest = SimulationEngine.load_manifest(SILENT_RELAY)
    base = _new_runtime()
    base.run_steps(300)
    touched = {
        str(e.payload.get("assetId"))
        for e in base.events
        if e.type == "sim.asset.status_changed"
    }
    for asset in sorted(manifest.assets, key=lambda a: a.id):
        if asset.id not in touched:
            return asset.id, asset.initial_status
    pytest.skip("scenario touches every asset; no bystander available")


def _real_stream_with_isolate(asset_id: str) -> list:
    runtime = _new_runtime()
    runtime.run_steps(10)
    runtime.execute_command(_isolate_command(runtime, asset_id))
    runtime.run_steps(300)
    return list(runtime.events)


def _execact_ref(engine: GhostBranchEngine, events: list) -> str:
    points = _enumerate(engine, events)
    execs = [p for p in points if p.decision_ref.startswith("execact:")]
    assert execs, "expected an executed-action decision point"
    return execs[0].decision_ref


def _enumerate(engine: GhostBranchEngine, events: list):
    from aegis_simulation.ghost_engine import _enumerate_decision_points

    return _enumerate_decision_points(events)


def _request(decision_ref: str, **kwargs) -> GhostBranchRequestV1:
    return GhostBranchRequestV1(
        schema_version=GHOST_BRANCH_REQUEST_SCHEMA_VERSION,
        decision_ref=decision_ref,
        **kwargs,
    )


def _compute(engine, events, request):
    return engine.compute_ghost(
        run_id=RUN_ID,
        seed=SEED,
        scenario_version_id=SCENARIO_VERSION,
        sim_events=events,
        request=request,
    )


def test_enumeration_finds_injected_executed_action() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    points = _enumerate(engine, events)
    execs = [p for p in points if p.decision_ref.startswith("execact:")]
    assert len(execs) == 1
    point = execs[0]
    assert point.scenario_command == ScenarioCommandTemplateV1.ISOLATE
    assert point.target_asset_id == asset_id
    assert point.kind.value == "executed_action"
    # Salient inaction windows are also enumerated for the adversary beats.
    assert any(p.decision_ref.startswith("inaction:") for p in points)


def test_substitute_produces_expected_asset_diff() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    ref = _execact_ref(engine, events)
    result = _compute(
        engine,
        events,
        _request(
            ref,
            mode=GhostBranchModeV1.SUBSTITUTE,
            alternate_command=ScenarioCommandTemplateV1.REVOKE_CREDENTIALS,
        ),
    )
    # Real isolates the bystander; the ghost revokes credentials instead — a crisp,
    # attacker-independent divergence on exactly that asset.
    diff = next((d for d in result.asset_diffs if d.asset_id == asset_id), None)
    assert diff is not None
    assert diff.real_status == "isolated"
    assert diff.ghost_status == "credentials_revoked"
    assert result.divergence_sequence > 0


def test_do_nothing_reverts_the_asset_to_untouched() -> None:
    engine = _engine()
    asset_id, initial_status = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    ref = _execact_ref(engine, events)
    result = _compute(engine, events, _request(ref, mode=GhostBranchModeV1.DO_NOTHING))
    diff = next((d for d in result.asset_diffs if d.asset_id == asset_id), None)
    assert diff is not None
    assert diff.real_status == "isolated"
    assert diff.ghost_status == initial_status


def test_same_request_twice_is_deterministic() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    ref = _execact_ref(engine, events)
    request = _request(
        ref,
        mode=GhostBranchModeV1.SUBSTITUTE,
        alternate_command=ScenarioCommandTemplateV1.REVOKE_CREDENTIALS,
    )
    first = _compute(engine, events, request)
    second = _compute(engine, events, request)
    assert first.result_hash == second.result_hash
    assert first.request_fingerprint == second.request_fingerprint
    assert [d.model_dump() for d in first.asset_diffs] == [
        d.model_dump() for d in second.asset_diffs
    ]


def test_compute_never_mutates_the_input_event_stream() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    before_len = len(events)
    before_last_seq = events[-1].sequence
    before_ids = [e.event_id for e in events]
    ref = _execact_ref(engine, events)
    _compute(
        engine,
        events,
        _request(
            ref,
            mode=GhostBranchModeV1.SUBSTITUTE,
            alternate_command=ScenarioCommandTemplateV1.ISOLATE,
        ),
    )
    # The engine reads the stream and builds throwaway runtimes; the real history is intact.
    assert len(events) == before_len
    assert events[-1].sequence == before_last_seq
    assert [e.event_id for e in events] == before_ids


def test_unknown_decision_ref_is_rejected() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    with pytest.raises(GhostBranchError) as excinfo:
        _compute(engine, events, _request("execact:999999", mode=GhostBranchModeV1.DO_NOTHING))
    assert excinfo.value.status_code == 404


def test_shift_is_deterministic_and_bounded() -> None:
    engine = _engine()
    asset_id, _ = _bystander_asset()
    events = _real_stream_with_isolate(asset_id)
    ref = _execact_ref(engine, events)
    request = _request(ref, mode=GhostBranchModeV1.SHIFT, shift_sim_seconds=-120)
    first = _compute(engine, events, request)
    second = _compute(engine, events, request)
    assert first.result_hash == second.result_hash
    assert first.steps_simulated <= 1000
