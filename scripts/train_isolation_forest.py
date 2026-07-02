#!/usr/bin/env python3
"""Train the Phase 16 Isolation Forest anomaly model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegis_ml.models.artifact_store import DEFAULT_MODEL_DIR
from aegis_ml.models.isolation_forest.train import train_isolation_forest, training_result_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Isolation Forest anomaly detector")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="Output directory for model artifacts",
    )
    parser.add_argument("--steps", type=int, default=300)
    args = parser.parse_args()
    result = train_isolation_forest(output_dir=args.output, steps=args.steps)
    print(json.dumps(training_result_to_json(result), indent=2))


if __name__ == "__main__":
    main()
