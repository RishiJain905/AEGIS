"""Scenario seed splits for baseline calibration and evaluation."""

from __future__ import annotations

TRAINING_SEEDS: tuple[int, ...] = (1, 11, 1006)
HOLDOUT_SEEDS: tuple[int, ...] = (1000, 1007, 1014)
SILENT_RELAY_SCENARIO_ID = "scenario:operation-silent-relay"
SILENT_RELAY_SCENARIO_PATH = "scenarios/operation-silent-relay"
GOLDEN_STEPS = 300
