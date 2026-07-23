"""Determinism tests for the Synthetic Training Scenario."""

from __future__ import annotations

from .helpers import TUTORIAL_SEED, run_scenario


def test_pinned_seed_produces_identical_hash() -> None:
    _, first = run_scenario(TUTORIAL_SEED)
    _, second = run_scenario(TUTORIAL_SEED)
    assert first == second


def test_different_seeds_produce_different_hashes() -> None:
    _, tutorial = run_scenario(TUTORIAL_SEED)
    _, other = run_scenario(TUTORIAL_SEED + 7)
    assert tutorial != other
