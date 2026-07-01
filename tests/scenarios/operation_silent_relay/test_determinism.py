"""Determinism tests for Operation Silent Relay."""

from __future__ import annotations

from .helpers import run_scenario


def test_same_seed_produces_identical_hash() -> None:
    _, first = run_scenario(1000)
    _, second = run_scenario(1000)
    assert first == second


def test_different_seeds_produce_different_hashes() -> None:
    _, hash_a = run_scenario(1000)
    _, hash_b = run_scenario(1006)
    assert hash_a != hash_b
