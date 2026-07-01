"""Unit tests for weighted branch selection."""

from __future__ import annotations

import random

from aegis_scenario_sdk.contracts.manifest import BranchOutcomeV1, OutcomeBranchDefinitionV1
from aegis_simulation_domain.branch_selection import select_weighted_branch


def _branch(branch_id: str, weight: float, group: str) -> OutcomeBranchDefinitionV1:
    return OutcomeBranchDefinitionV1(
        id=branch_id,
        label=branch_id,
        weight=weight,
        trigger_condition="test",
        outcomes=[BranchOutcomeV1(target_ref="hidden-cause-01")],
        branch_group=group,
    )


def test_select_weighted_branch_is_deterministic() -> None:
    branches = [
        _branch("branch-a", 0.5, "test-group"),
        _branch("branch-b", 0.5, "test-group"),
    ]
    stream_a = random.Random(42)
    stream_b = random.Random(42)
    assert select_weighted_branch(
        branches, branch_group="test-group", candidate_branch_ids=[], stream=stream_a
    ) == select_weighted_branch(
        branches, branch_group="test-group", candidate_branch_ids=[], stream=stream_b
    )


def test_select_weighted_branch_respects_group_filter() -> None:
    branches = [
        _branch("branch-a", 1.0, "group-a"),
        _branch("branch-b", 1.0, "group-b"),
    ]
    stream = random.Random(1)
    selected = select_weighted_branch(
        branches, branch_group="group-a", candidate_branch_ids=[], stream=stream
    )
    assert selected == "branch-a"
