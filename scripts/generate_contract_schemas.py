#!/usr/bin/env python3
"""Generate JSON Schemas from canonical Pydantic contract models."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_contracts.fixtures import FIXTURE_MODEL_MAP

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "tests" / "contract" / "fixtures" / "schemas"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in sorted(FIXTURE_MODEL_MAP.items()):
        schema_path = SCHEMA_DIR / f"{name}.schema.json"
        schema = model.model_json_schema(mode="serialization")
        schema_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {schema_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
