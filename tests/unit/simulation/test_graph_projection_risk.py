"""The graph projection publishes live risk, not the scenario's seed value.

Regression cover for the owner-reported inert RISK SCORE: ``GraphNodeV1.risk_score`` was
``AssetState.risk_score``, which is assigned ``initial_risk_score`` once when the world is
materialized from the manifest and is never written again by anything. Every asset in a
finished run therefore carried its authored seed value — measured across the whole live
run ``run_HAQWCJAZ9P7CVFZVKMNEH9WXQ5``, every node held exactly one distinct risk value
from tick 0 to tick 1043, spanning 0.00-0.20, with a ``suspicious`` critical service
(0.12) reading *lower* than an untouched vendor laptop (0.20).

Offline: builds a runtime from the fixture scenario package, no database.
"""

from __future__ import annotations

from pathlib import Path

from aegis_contracts.graph import NodeStatus
from aegis_contracts.killchain import ContainmentStatus
from aegis_graph_risk.posture import posture_risk
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SimulationRuntime

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = WORKSPACE_ROOT / "scenarios" / "_fixtures" / "valid-minimal"


def _runtime() -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(PACKAGE_DIR)
    return SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id="scenario-version:1.0.0-fixture",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )


def _risk_of(runtime: SimulationRuntime, asset_id: str) -> float:
    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=1)
    return next(node for node in snapshot.nodes if node.id == asset_id).risk_score


def test_compromise_raises_the_projected_risk_score() -> None:
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    at_rest = _risk_of(runtime, asset.id)

    asset.apply_status(NodeStatus.COMPROMISED.value)
    compromised = _risk_of(runtime, asset.id)

    assert compromised > at_rest
    assert compromised >= 0.8


def test_a_compromised_asset_outranks_every_untouched_asset() -> None:
    runtime = _runtime()
    assets = sorted(runtime.world.assets.values(), key=lambda item: item.id)
    assert len(assets) > 1, "fixture needs more than one asset to rank"
    assets[0].apply_status(NodeStatus.COMPROMISED.value)

    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=1)
    by_id = {node.id: node.risk_score for node in snapshot.nodes}
    compromised = by_id.pop(assets[0].id)

    assert all(compromised > other for other in by_id.values())


def test_containment_reads_as_risk_reduced_from_the_compromised_peak() -> None:
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    at_rest = _risk_of(runtime, asset.id)

    asset.apply_status(NodeStatus.COMPROMISED.value)
    peak = _risk_of(runtime, asset.id)

    asset.apply_status(ContainmentStatus.ISOLATED.value)
    contained = _risk_of(runtime, asset.id)

    assert at_rest < contained < peak


def test_observing_an_asset_does_not_pretend_it_is_safer() -> None:
    """Observation is not a response: watching a compromised host keeps it at its peak."""
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    asset.apply_status(NodeStatus.COMPROMISED.value)
    peak = _risk_of(runtime, asset.id)

    asset.apply_status(ContainmentStatus.OBSERVED.value)

    assert _risk_of(runtime, asset.id) == peak


def test_at_rest_risk_keeps_the_scenario_authored_baseline_as_a_floor() -> None:
    runtime = _runtime()
    for asset in runtime.world.assets.values():
        projected = _risk_of(runtime, asset.id)
        assert projected >= asset.risk_score
        assert projected == posture_risk(
            asset.effective_status,
            asset.criticality,
            authored_floor=asset.risk_score,
        )


def test_projection_is_deterministic_and_leaves_world_state_alone() -> None:
    """Risk is derived at projection time, so no world state (and no checkpoint) changes."""
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    asset.apply_status(NodeStatus.COMPROMISED.value)
    seeded_risk = asset.risk_score

    first = build_graph_snapshot_from_runtime(runtime, sequence=1)
    second = build_graph_snapshot_from_runtime(runtime, sequence=1)

    assert [node.risk_score for node in first.nodes] == [node.risk_score for node in second.nodes]
    assert asset.risk_score == seeded_risk
