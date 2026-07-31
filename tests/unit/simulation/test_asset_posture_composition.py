"""An asset's posture and its applied controls must not erase each other.

The defect this covers: ``effect.set_asset_status`` overwrote a single ``status`` field,
so the response toolkit destroyed the very signal it was responding to. Putting a
compromised host under observation replaced ``compromised`` with ``observed`` — the world
forgot there was an intrusion, the disruption model stopped seeing the attacker's
foothold, and the after-action could no longer say what had been compromised or when.

Posture (what the attacker did) and applied controls (what we did about it) are now
separate facts on the asset, composed only at projection time. These tests pin that:
every response verb over an active compromise, through the real approved-action path, the
cold rebuild from the event stream, and a checkpoint round-trip.

Offline: builds runtimes from the fixture scenario package, no database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import ActorRef, ActorType
from aegis_contracts.graph import NodeStatus
from aegis_contracts.killchain import AttackTactic, ContainmentStatus
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.simulation import (
    SimulationCommandType,
    SimulationCommandV1,
)
from aegis_contracts.versioning import SIMULATION_COMMAND_SCHEMA_VERSION
from aegis_policy.commands import COMMAND_STATUS_MAP
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SimulationRuntime
from aegis_simulation_domain.world_state import AssetState
from pydantic import ValidationError

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = WORKSPACE_ROOT / "scenarios" / "_fixtures" / "valid-minimal"

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _runtime() -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(PACKAGE_DIR)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id="scenario-version:1.0.0-fixture",
        run_id=RUN_ID,
    )
    runtime.start()
    return runtime


def _any_asset_id(runtime: SimulationRuntime) -> str:
    return sorted(runtime.world.assets)[0]


def _execute(
    runtime: SimulationRuntime, asset_id: str, command: ScenarioCommandTemplateV1
) -> list:
    """Apply a response command exactly as the approval pipeline does."""
    return runtime.execute_command(
        SimulationCommandV1(
            schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
            command_id=f"cmd-{command.value}-{asset_id}-{runtime.world.next_sequence}",
            command_type=SimulationCommandType.EXECUTE,
            run_id=runtime.run_id,
            actor=ActorRef(type=ActorType.OPERATOR, id="asset:test-operator"),
            authorization_token="test-approval",
            payload={
                "pluginId": "effect.set_asset_status",
                "targetAssetId": asset_id,
                "config": {"assetId": asset_id, "status": COMMAND_STATUS_MAP[command]},
            },
        )
    )


def test_observe_on_a_compromised_asset_keeps_the_compromise() -> None:
    """The headline defect: watching an intrusion must not delete it."""
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.COMPROMISED.value

    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)

    asset = runtime.world.assets[asset_id]
    assert asset.status == NodeStatus.COMPROMISED.value
    assert ContainmentStatus.OBSERVED.value in asset.applied_controls
    # ...and the operator still sees a compromised asset, now known to be watched.
    assert asset.effective_status == NodeStatus.COMPROMISED.value


def test_isolate_on_a_compromised_asset_reads_contained_and_remembers_why() -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.COMPROMISED.value

    _execute(runtime, asset_id, ScenarioCommandTemplateV1.ISOLATE)

    asset = runtime.world.assets[asset_id]
    assert asset.effective_status == NodeStatus.CONTAINED.value
    assert asset.status == NodeStatus.COMPROMISED.value
    assert ContainmentStatus.ISOLATED.value in asset.applied_controls


@pytest.mark.parametrize("command", sorted(COMMAND_STATUS_MAP, key=lambda c: c.value))
def test_no_response_command_erases_an_active_compromise(
    command: ScenarioCommandTemplateV1,
) -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.COMPROMISED.value

    _execute(runtime, asset_id, command)

    asset = runtime.world.assets[asset_id]
    assert asset.status == NodeStatus.COMPROMISED.value
    assert asset.applied_controls == (COMMAND_STATUS_MAP[command],)


def test_controls_accumulate_in_application_order_without_duplicates() -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)

    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)
    _execute(runtime, asset_id, ScenarioCommandTemplateV1.ISOLATE)
    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)

    asset = runtime.world.assets[asset_id]
    assert asset.applied_controls == (
        ContainmentStatus.OBSERVED.value,
        ContainmentStatus.ISOLATED.value,
    )


def test_an_observed_but_uncompromised_asset_reads_under_investigation() -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.NORMAL.value

    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)

    assert (
        runtime.world.assets[asset_id].effective_status
        == NodeStatus.UNDER_INVESTIGATION.value
    )


def test_graph_projection_shows_the_composed_status_and_the_controls() -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.COMPROMISED.value
    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)

    snapshot = build_graph_snapshot_from_runtime(runtime)
    node = next(node for node in snapshot.nodes if node.id == asset_id)

    assert node.status == NodeStatus.COMPROMISED
    assert node.applied_controls == [ContainmentStatus.OBSERVED.value]


def test_checkpoint_round_trip_preserves_posture_and_controls() -> None:
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    runtime.world.assets[asset_id].status = NodeStatus.COMPROMISED.value
    _execute(runtime, asset_id, ScenarioCommandTemplateV1.OBSERVE)
    _execute(runtime, asset_id, ScenarioCommandTemplateV1.ISOLATE)

    checkpoint = runtime.checkpoint()
    restored = _runtime()
    restored.restore(checkpoint)

    asset = restored.world.assets[asset_id]
    assert asset.status == NodeStatus.COMPROMISED.value
    assert asset.applied_controls == (
        ContainmentStatus.OBSERVED.value,
        ContainmentStatus.ISOLATED.value,
    )


def test_a_pre_split_checkpoint_restores_its_containment_as_a_control() -> None:
    """Checkpoints written before the split collapsed everything into ``status``.

    Restoring one straight through would leave a posture the graph vocabulary rejects and
    a control set the disruption model cannot see, so a resumed run would silently forget
    every containment the operator had applied.
    """
    runtime = _runtime()
    asset_id = _any_asset_id(runtime)
    snapshot = runtime.checkpoint().world_state
    legacy = snapshot.model_copy(
        update={
            "assets": [
                asset.model_copy(
                    update={
                        "status": ContainmentStatus.ISOLATED.value,
                        "applied_controls": [],
                    }
                )
                if asset.id == asset_id
                else asset
                for asset in snapshot.assets
            ]
        }
    )

    restored = _runtime()
    restored.world.restore_from_snapshot(legacy)

    asset = restored.world.assets[asset_id]
    assert asset.applied_controls == (ContainmentStatus.ISOLATED.value,)
    assert asset.status == NodeStatus.CONTAINED.value
    assert asset.effective_status == NodeStatus.CONTAINED.value


def test_cold_rebuild_from_the_event_stream_composes_the_same_world() -> None:
    """A rebuilt runtime must agree with the live one it was rebuilt from.

    The rebuild re-applies persisted ``sim.asset.status_changed`` events, which carry only
    the single value that was applied — the same shape runs recorded before the split
    carry — so this also pins that old streams replay into the composed world.
    """
    live = _runtime()
    asset_id = _any_asset_id(live)
    live.world.assets[asset_id].status = NodeStatus.COMPROMISED.value
    events = _execute(live, asset_id, ScenarioCommandTemplateV1.OBSERVE)
    events += _execute(live, asset_id, ScenarioCommandTemplateV1.ISOLATE)

    rebuilt = _runtime()
    rebuilt.world.assets[asset_id].status = NodeStatus.COMPROMISED.value
    for event in events:
        if event.type == "sim.asset.status_changed":
            RunCommandService._apply_executed_effect(rebuilt, event)

    live_asset = live.world.assets[asset_id]
    rebuilt_asset = rebuilt.world.assets[asset_id]
    assert rebuilt_asset.status == live_asset.status
    assert rebuilt_asset.applied_controls == live_asset.applied_controls


def test_an_observed_asset_reports_telemetry_at_twice_the_cadence() -> None:
    """"Observe" has to *do* something: it doubles what detection gets to see.

    Watching an asset never changes what is happening on it — only how much of it reaches
    the defender — so the lever is sampling cadence, not the odds of a bad event.
    """
    runtime = _runtime()
    generator = sorted(runtime.world.generators.values(), key=lambda g: g.generator_id)[0]
    asset_id = generator.target_asset_id
    baseline_interval = generator.interval_sim_seconds

    before = generator.next_sim_time
    runtime.advance(before)
    unobserved_gap = (generator.next_sim_time - before).total_seconds()

    runtime.world.assets[asset_id].apply_status(ContainmentStatus.OBSERVED.value)
    before = generator.next_sim_time
    runtime.advance(before)
    observed_gap = (generator.next_sim_time - before).total_seconds()

    assert unobserved_gap == baseline_interval
    assert observed_gap == baseline_interval // 2


def test_a_technique_may_not_author_a_control_as_its_compromise_status() -> None:
    """``contained`` is the one word both vocabularies use, and it belongs to the defender.

    Authored as an attacker outcome it would split the two paths apart: the live engine
    writes ``compromise_status`` straight to the posture, while the cold rebuild routes the
    resulting event through ``apply_status`` and files it as a control. Same stream, two
    different worlds — so it is rejected where scenarios are authored.
    """
    from aegis_scenario_sdk.contracts.manifest import KillChainTechniqueV1

    base = {
        "id": "technique-a",
        "tactic": AttackTactic.EXECUTION.value,
        "attackTechniqueId": "T1059",
        "name": "Command execution",
        "anchor": {"mode": "by_id", "assetId": "asset:svc-auth-service"},
        "dwellSimSeconds": 60.0,
    }

    assert (
        KillChainTechniqueV1.model_validate(
            {**base, "compromiseStatus": NodeStatus.COMPROMISED.value}
        ).compromise_status
        is NodeStatus.COMPROMISED
    )
    with pytest.raises(ValidationError):
        KillChainTechniqueV1.model_validate(
            {**base, "compromiseStatus": NodeStatus.CONTAINED.value}
        )


def test_apply_status_routes_each_vocabulary_to_its_own_field() -> None:
    asset = AssetState(
        id="asset:unit",
        asset_type="service",
        status=NodeStatus.NORMAL.value,
        risk_score=0.0,
        criticality=0.5,
        zone_id="zone:test",
    )

    asset.apply_status(ContainmentStatus.OBSERVED.value)
    asset.apply_status(NodeStatus.COMPROMISED.value)

    assert asset.status == NodeStatus.COMPROMISED.value
    assert asset.applied_controls == (ContainmentStatus.OBSERVED.value,)
    assert asset.revision == 2
