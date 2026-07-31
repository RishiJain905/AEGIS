"""World-state status -> operator graph status projection.

Regression cover for the defect that stranded live runs: an operator containment action
sets an asset's *world* status to a response-toolkit value ("isolated"), the graph
projection passed it straight into ``GraphSnapshotV1``, and the contract rejected it. The
snapshot write lives inside every emitting STEP/START/RESUME command, so from the first
containment onward the run could not step *or* resume — it sat paused forever, and every
``POST /runs/{id}/step`` answered 500.

Offline: builds a runtime from the fixture scenario package, no database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts.graph import NodeStatus
from aegis_contracts.killchain import ContainmentStatus, project_node_status
from aegis_policy.commands import COMMAND_STATUS_MAP
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation_domain import SimulationEngine

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = WORKSPACE_ROOT / "scenarios" / "_fixtures" / "valid-minimal"


def _runtime() -> object:
    manifest = SimulationEngine.load_manifest(PACKAGE_DIR)
    return SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id="scenario-version:1.0.0-fixture",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )


@pytest.mark.parametrize("world_status", sorted(status.value for status in ContainmentStatus))
def test_every_containment_status_projects_to_a_valid_node_status(world_status: str) -> None:
    assert project_node_status(world_status) in set(NodeStatus)


@pytest.mark.parametrize("command", sorted(COMMAND_STATUS_MAP, key=lambda item: item.value))
def test_every_allowlisted_command_status_survives_snapshot_validation(command: object) -> None:
    """The response toolkit is the source of these statuses, so all of them must project.

    Parameterizing over ``COMMAND_STATUS_MAP`` rather than a hand-written list means a new
    allowlisted command that forgets its projection entry fails here instead of in
    production, where it strands the run it was used on.
    """
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    asset.status = COMMAND_STATUS_MAP[command]  # type: ignore[index]

    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=1)

    node = next(item for item in snapshot.nodes if item.id == asset.id)
    assert node.status in set(NodeStatus)


def test_isolate_projects_as_contained_not_as_an_invalid_status() -> None:
    """The exact live failure: "Isolate service" on an asset, then project the graph."""
    runtime = _runtime()
    asset = next(iter(runtime.world.assets.values()))
    asset.status = ContainmentStatus.ISOLATED.value

    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=1)

    node = next(item for item in snapshot.nodes if item.id == asset.id)
    assert node.status is NodeStatus.CONTAINED


def test_attacker_and_baseline_statuses_pass_through_unchanged() -> None:
    for status in NodeStatus:
        assert project_node_status(status.value) is status


def test_observation_only_controls_do_not_claim_containment() -> None:
    """OBSERVE / INCREASE_MONITORING change what is watched, not whether it is contained."""
    for status in (ContainmentStatus.OBSERVED, ContainmentStatus.HEIGHTENED_MONITORING):
        assert project_node_status(status.value) is NodeStatus.UNDER_INVESTIGATION


def test_unknown_status_degrades_instead_of_raising() -> None:
    """A projection that raises wedges the run; the whole point is that it cannot."""
    assert project_node_status("something_nobody_authored") is NodeStatus.UNDER_INVESTIGATION
