# Operation Silent Relay

Flagship AEGIS v1.0 scenario package (Phase 10).

## Contents

| File | Purpose |
|------|---------|
| `manifest.yaml` | ScenarioManifestV1 — 38 assets, 8 zones, 4 causes, 3 response branches |
| `golden-seeds.yaml` | Deterministic seed registry |
| `expected-evidence.yaml` | Evidence chains and false-hypothesis contradictions |
| `briefing.md` | Operator briefing |
| `presentation/overview.md` | Narrative metadata for cinematic phases |

## Validate

```bash
uv run aegis-scenario validate scenarios/operation-silent-relay
uv run aegis-simulator determinism-check --scenario scenarios/operation-silent-relay --seed 1000 --steps 300
```

## Regenerate manifest

```bash
uv run python scripts/generate-silent-relay-manifest.py
```
