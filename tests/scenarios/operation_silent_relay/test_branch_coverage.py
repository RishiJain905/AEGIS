"""Branch and cause coverage for Operation Silent Relay."""

from __future__ import annotations

from .helpers import load_golden_seeds, run_scenario


def test_each_root_cause_reachable() -> None:
    registry = load_golden_seeds()
    cause_seeds = [entry for entry in registry["seeds"] if entry["seed"] >= 1000]
    causes = {entry["rootCauseBranch"] for entry in cause_seeds}
    assert causes == {
        "branch-cause-credentials",
        "branch-cause-maintenance",
        "branch-cause-misuse",
        "branch-cause-deployment",
    }
    for entry in cause_seeds:
        runtime, _ = run_scenario(entry["seed"])
        assert runtime.world.selected_branches["root-cause"] == entry["rootCauseBranch"]


def test_each_response_branch_reachable() -> None:
    registry = load_golden_seeds()
    responses = {entry["responseBranch"] for entry in registry["seeds"]}
    assert "branch-response-contain" in responses
    assert "branch-response-investigate" in responses
    assert "branch-response-remediate" in responses


def test_same_cause_different_response_diverges() -> None:
    _, hash_remediate = run_scenario(1)
    _, hash_contain = run_scenario(11)
    assert hash_remediate != hash_contain
