#!/usr/bin/env python3
"""Evaluate Phase 15 rules on scenario holdout seeds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aegis_incidents.evaluation import run_holdout_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate detection rules on holdout seeds")
    parser.add_argument("--output", type=Path, default=Path("models/evaluation/rules/holdout-v1"))
    parser.add_argument("--steps", type=int, default=300)
    args = parser.parse_args()

    evaluation = run_holdout_evaluation(steps=args.steps)
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / "evaluation_run.json"
    output_path.write_text(
        json.dumps(evaluation.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evaluation.model_dump(mode="json", by_alias=True), indent=2))


if __name__ == "__main__":
    main()
