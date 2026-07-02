#!/usr/bin/env python3
"""Calibrate statistical baselines from training-seed simulations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.baselines.calibration import calibrate_baselines_from_vectors
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, TRAINING_SEEDS
from aegis_ml.baselines.store import DEFAULT_BASELINE_DIR, save_baseline
from aegis_ml.features import compute_features_from_events


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate detection baselines from training seeds"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BASELINE_DIR,
        help="Output directory for baseline artifacts",
    )
    parser.add_argument("--steps", type=int, default=300)
    args = parser.parse_args()

    vectors = []
    for seed in TRAINING_SEEDS:
        run_id, events = run_scenario_events(seed=seed, steps=args.steps)
        result = compute_features_from_events(run_id=run_id, events=events)
        vectors.extend(result.vectors)

    baseline = calibrate_baselines_from_vectors(vectors, training_seeds=list(TRAINING_SEEDS))
    manifest = save_baseline(baseline, output_dir=args.output, holdout_seeds=list(HOLDOUT_SEEDS))
    print(json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2))


if __name__ == "__main__":
    main()
