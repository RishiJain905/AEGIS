#!/usr/bin/env python3
"""Generate JSON Schemas from canonical Scenario SDK Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.contracts.package import ScenarioPackageManifestV1

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "scenario" / "v1"

MODELS = {
    "manifest": ScenarioManifestV1,
    "package-manifest": ScenarioPackageManifestV1,
}


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema_path = SCHEMA_DIR / f"{name}.schema.json"
        schema = model.model_json_schema(mode="serialization")
        schema_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {schema_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
