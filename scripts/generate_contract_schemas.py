#!/usr/bin/env python3
"""Generate JSON Schemas from canonical Pydantic contract models.

After writing schemas, run Prettier so `pnpm format:check` stays green:

    pnpm exec prettier --config config/.prettierrc.json --write \\
      tests/contract/fixtures/schemas
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aegis_contracts.fixtures import FIXTURE_MODEL_MAP

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "tests" / "contract" / "fixtures" / "schemas"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    only = {name for name in sys.argv[1:] if name}
    for name, model in sorted(FIXTURE_MODEL_MAP.items()):
        if only and name not in only:
            continue
        schema_path = SCHEMA_DIR / f"{name}.schema.json"
        schema = model.model_json_schema(mode="serialization")
        schema_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {schema_path.relative_to(ROOT)}")

    prettier = subprocess.run(
        [
            "pnpm",
            "exec",
            "prettier",
            "--config",
            "config/.prettierrc.json",
            "--write",
            str(SCHEMA_DIR.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=False,
    )
    if prettier.returncode != 0:
        raise SystemExit(
            "Schema generation succeeded but Prettier formatting failed. "
            "Install workspace deps and re-run."
        )


if __name__ == "__main__":
    main()
