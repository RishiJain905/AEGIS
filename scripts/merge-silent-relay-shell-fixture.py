#!/usr/bin/env python3
"""Merge Silent Relay fixture patch into shell-dataset.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_DATASET = ROOT / "apps" / "web" / "fixtures" / "shell-dataset.json"
PATCH = ROOT / "apps" / "web" / "fixtures" / "silent-relay" / "shell-dataset-patch.json"


def merge_unique(items: list[dict], new_items: list[dict], key: str) -> list[dict]:
    merged = {item[key]: item for item in items}
    for item in new_items:
        merged[item[key]] = item
    return list(merged.values())


def main() -> None:
    dataset = json.loads(SHELL_DATASET.read_text(encoding="utf-8"))
    patch = json.loads(PATCH.read_text(encoding="utf-8"))
    dataset["scenarios"] = merge_unique(dataset["scenarios"], patch["scenarios"], "id")
    dataset["scenarioVersions"] = merge_unique(
        dataset["scenarioVersions"], patch["scenarioVersions"], "id"
    )
    dataset["runs"] = merge_unique(dataset["runs"], patch["runs"], "id")
    dataset["incidents"] = merge_unique(dataset["incidents"], patch["incidents"], "id")
    dataset["alerts"] = merge_unique(dataset["alerts"], patch["alerts"], "id")
    dataset["graphSnapshots"] = merge_unique(
        dataset["graphSnapshots"], patch["graphSnapshots"], "runId"
    )
    SHELL_DATASET.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {SHELL_DATASET}")


if __name__ == "__main__":
    main()
