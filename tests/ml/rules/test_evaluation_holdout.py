"""Holdout evaluation tests."""

from aegis_ml.baselines.splits import HOLDOUT_SEEDS, TRAINING_SEEDS


def test_training_and_holdout_seeds_are_disjoint() -> None:
    assert set(TRAINING_SEEDS).isdisjoint(set(HOLDOUT_SEEDS))
