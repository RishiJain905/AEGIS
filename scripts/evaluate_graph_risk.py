#!/usr/bin/env python3
"""Evaluate graph risk propagation on holdout scenario seeds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegis_ml.baselines.splits import HOLDOUT_SEEDS, TRAINING_SEEDS
from aegis_ml.evaluation.risk_evaluation import evaluate_graph_risk_holdout

OUTPUT_DIR = Path("models/evaluation/graph-risk/holdout-v1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate graph risk on holdout seeds")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    result = evaluate_graph_risk_holdout(steps=args.steps, output_dir=args.output_dir)
    print(json.dumps(result, indent=2))
    print(f"Training seeds (excluded): {sorted(TRAINING_SEEDS)}")
    print(f"Holdout seeds: {sorted(HOLDOUT_SEEDS)}")


if __name__ == "__main__":
    main()
