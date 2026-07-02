# Graph Risk Propagation (Phase 17)

Deterministic bounded graph-risk propagation for AEGIS v1.0. This is **not** a graph neural network — it is transparent rule-based propagation with evidence-backed explanation paths.

## Algorithm (`graph-risk-v1`)

- **Inputs:** Phase 15 `AlertV1` and Phase 16 model-derived alerts normalized to `RiskInputV1`
- **Topology:** `GraphSnapshotV1` from PostgreSQL / simulation projection (Phase 05)
- **Direct risk:** max signal strength at origin asset
- **Propagated risk:** max bounded contribution along eligible directed edges up to `maxHops` (default 4)
- **Decay:** per-hop `distanceDecayFactor` (default 0.65); temporal decay from signal age
- **Criticality:** target asset criticality amplifies received risk (capped)
- **Output:** `AssetRiskScoreV1` with `total`, `direct`, `propagated`, and `topContributions`

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/risk/config` | Default `RiskEngineConfigV1` |
| POST | `/api/v1/risk/compute` | Run propagation for a run |
| GET | `/api/v1/risk/scores/{runId}` | Latest per-asset scores |
| GET | `/risk/observability` | Phase 17 observability page |

## Operational commands

```bash
uv run python scripts/run_graph_risk.py --run-id <run_id>
uv run python scripts/evaluate_graph_risk.py --steps 300
uv run alembic upgrade head
```

## Realtime

- `risk.score.computed` — persisted score payload
- `risk.projection.updated` — `RiskProjectionDeltaV1` applied to graph node `riskScore` in the command centre

## Evaluation

Holdout artifacts: `models/evaluation/graph-risk/holdout-v1/`

Hidden scenario truth remains evaluation-only and is not used during live propagation.
