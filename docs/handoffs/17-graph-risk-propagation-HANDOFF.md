# Phase 17 Handoff — Graph Risk Propagation

## Status

`COMPLETE`

## Implemented

Phase 17 deliverables per `docs/AEGIS-v1.0-Agent-Specs/detection-and-machine-learning/17-graph-risk-propagation.md`:

- Versioned risk contracts (`RiskInputV1`, `AssetRiskScoreV1`, `RiskContributionV1`, `RiskExplanationPathV1`, `RiskEngineConfigV1`, `RiskProjectionDeltaV1`)
- Python `aegis-graph-risk` deterministic bounded BFS propagation (`graph-risk-v1`)
- Normalization from Phase 15 alerts and Phase 16 model scores
- PostgreSQL `asset_risk_scores` persistence + migration `004_asset_risk_scores`
- `risk_pipeline.py` + `risk_promotion.py` with `risk.score.computed` and `risk.projection.updated` events
- API routes `/api/v1/risk/*` and `/risk/observability`
- Realtime graph projection via `event-projector.ts`
- Command centre inspector with direct/propagated breakdown and explanation paths
- Evaluation artifacts under `models/evaluation/graph-risk/holdout-v1/`
- ADR 0018, `docs/ml/graph-risk.md`, tests, demo capture script

**Explicitly not implemented:** GNN, LLM analyst, automated containment, Phase 18 model-provider abstraction.

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/risk.py`, `packages/contracts-ts/src/risk.ts` |
| Engine | `packages/graph-risk/src/aegis_graph_risk/**` |
| ML | `services/ml/src/aegis_ml/risk/**`, `services/ml/src/aegis_ml/evaluation/risk_evaluation.py` |
| Incidents | `services/incidents/src/aegis_incidents/risk_pipeline.py`, `risk_promotion.py` |
| Persistence | `PostgresRiskScoreRepository`, migration `004_asset_risk_scores.py` |
| API | `apps/api/src/aegis_api/risk/**` |
| Frontend | `apps/web/features/risk/**`, fixture `risk-scores-fixture.ts`, capture script |
| Tests | `tests/ml/risk/**`, `tests/integration/risk/test_risk_persistence.py` |
| Docs | `docs/ml/graph-risk.md`, ADR `0018-graph-risk-propagation.md` |

## Contracts introduced or changed

| Contract | Version | Notes |
|----------|---------|-------|
| `RiskInputV1` | schema v1 | Normalized origin signal |
| `AssetRiskScoreV1` | schema v1 | total/direct/propagated decomposition |
| `RiskContributionV1` | schema v1 | Material contribution + path |
| `RiskExplanationPathV1` | schema v1 | Ordered nodes/edges + decay metadata |
| `RiskEngineConfigV1` | schema v1 | Algorithm `graph-risk-v1` |
| `RiskProjectionDeltaV1` | schema v1 | Graph overlay batch |
| Event types | v1 | `risk.score.computed`, `risk.projection.updated` |
| `WORKSPACE_VERSION` | `0.0.0-phase17` | Compatibility bump |

## Database migrations

- `004_asset_risk_scores.py` — `asset_risk_scores` table

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run mypy apps services packages` | **KNOWN ISSUE** — pre-existing `apps/api/src/aegis_api/db/session.py` duplicate module path (documented Phase 16 precedent) |
| `uv run pytest -q` | **PASS** — 423 passed, 33 skipped |
| `uv run pytest tests/ml/risk -q` | **PASS** — 20 passed |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm lint` | **PASS** |
| `pnpm test` | **PASS** — 57 tests |
| `uv run python scripts/evaluate_graph_risk.py --steps 120` | **PASS** — holdout artifacts written |
| `node apps/web/scripts/capture-graph-risk-demo.mjs` | **PASS** — 8 screenshots captured |

## Architecture decisions and ADRs

- **Created:** [0018-graph-risk-propagation.md](../AEGIS-v1.0-Agent-Specs/adrs/0018-graph-risk-propagation.md) (Status: **Proposed**)

## Acceptance criteria evidence

1. **Cycles cannot create runaway amplification:** `test_cycle_bounds.py` — all scores ≤ 1.0 on cyclic graph
2. **Every propagated contribution has an explanation path:** `test_explanation_paths.py`
3. **Live and historical results agree for identical state:** deterministic checksum in `test_propagation_determinism.py`; historical replay via `get_at_sequence` in API
4. **Risk remains bounded, deterministic, and decomposable:** `test_incremental_parity.py`, `test_validation_failures.py`

## Prohibited-shortcut confirmation

No GNN, no renderer-side authoritative risk math, no competing graph topology, no hidden-truth in runtime propagation, validation commands executed as recorded.
