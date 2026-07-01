"""Tests for branch-gated scheduled events."""

from __future__ import annotations

from pathlib import Path

from aegis_simulation_domain import SimulationEngine


def test_branch_gated_event_skipped_when_branch_mismatches() -> None:
    manifest = SimulationEngine.load_manifest(Path("scenarios/operation-silent-relay"))
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id="scenario-version:1.0.0",
    )
    runtime.start()
    runtime.run_steps(300)
    statuses = {asset.id: asset.status for asset in runtime.world.assets.values()}
    # Seed 1000 selects credentials path, not deployment — logistics API suspicious
    # only on deployment path effect
    assert statuses["asset:svc-logistics-api"] != "suspicious" or runtime.world.selected_branches[
        "root-cause"
    ] == "branch-cause-deployment"
