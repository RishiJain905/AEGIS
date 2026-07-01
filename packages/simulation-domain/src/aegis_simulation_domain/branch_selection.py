"""Deterministic weighted branch selection from manifest definitions."""

from __future__ import annotations

import random

from aegis_scenario_sdk.contracts.manifest import OutcomeBranchDefinitionV1


def select_weighted_branch(
    branches: list[OutcomeBranchDefinitionV1],
    *,
    branch_group: str,
    candidate_branch_ids: list[str],
    stream: random.Random,
) -> str | None:
    filtered = [branch for branch in branches if branch.branch_group == branch_group]
    if candidate_branch_ids:
        allowed = set(candidate_branch_ids)
        filtered = [branch for branch in filtered if branch.id in allowed]
    if not filtered:
        return None
    total_weight = sum(branch.weight for branch in filtered)
    if total_weight <= 0.0:
        return filtered[0].id
    threshold = stream.random() * total_weight
    cumulative = 0.0
    for branch in filtered:
        cumulative += branch.weight
        if threshold <= cumulative:
            return branch.id
    return filtered[-1].id
