"""The single deterministic attack path must fire within the tutorial horizon."""

from __future__ import annotations

from .helpers import STEPS, TUTORIAL_SEED, event_types_for_run, run_scenario


def test_single_attack_branch_selected() -> None:
    runtime, _ = run_scenario(TUTORIAL_SEED)
    # One attack path, no branch RNG: the weight-1.0 branch is always selected.
    assert runtime.world.selected_branches["attack"] == "branch-attack-primary"  # type: ignore[attr-defined]


def test_attack_reaches_exfiltration_within_horizon() -> None:
    runtime, _ = run_scenario(TUTORIAL_SEED)
    statuses = {asset.id: asset.status for asset in runtime.world.assets.values()}  # type: ignore[attr-defined]
    # Full intrusion chain resolves before the 120-step horizon is exhausted.
    assert statuses["asset:device-workstation-alpha"] == "compromised"
    assert statuses["asset:svc-file-server"] == "suspicious"
    assert statuses["asset:database-student-records"] == "under_investigation"


def test_hidden_conditions_trigger_and_reveal() -> None:
    types = event_types_for_run(TUTORIAL_SEED)
    # Fog-of-war hidden conditions play correctly (triggered then revealed).
    assert "sim.hidden_condition.triggered" in types
    assert "sim.hidden_condition.revealed" in types
    assert "sim.branch.selected" in types


def test_horizon_produces_baseline_and_attack_telemetry() -> None:
    types = event_types_for_run(TUTORIAL_SEED)
    # Baseline noise plus the attack-specific signal telemetry are both present.
    assert "telemetry.process.activity" in types
    assert "telemetry.authentication.failed" in types
    assert "telemetry.network.connection" in types
    assert "telemetry.database.query" in types


def test_deterministic_across_full_horizon() -> None:
    runtime, _ = run_scenario(TUTORIAL_SEED, steps=STEPS)
    assert runtime.world.status.value == "running"  # type: ignore[attr-defined]
