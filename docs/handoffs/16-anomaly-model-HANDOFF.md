# Phase 16 Handoff — Anomaly Model

## Status

`READY FOR VALIDATION`

## Implemented

Phase 16 deliverables per `docs/AEGIS-v1.0-Agent-Specs/detection-and-machine-learning/16-anomaly-model.md`:

- Versioned model contracts in `aegis_contracts.models` / `@aegis/contracts-ts` models module
- Extended `ModelManifestV1` and additive `AlertV1` fields (`anomalyExplanation`, `modelVersionId`)
- Isolation Forest training pipeline with deterministic seed splits and Phase 14 feature vectors
- Artifact store with checksum/schema verification and fail-closed load
- Batch and online inference with structured `AnomalyExplanationV1`
- Parallel model detection path with Phase 15 rules preserved and graceful fallback
- `model.score.recorded` events + UI invalidation
- API routes and `/models/observability` page
- Evaluation artifacts comparing model vs Phase 15 rules on holdout seeds
- Documentation, ADR 0017, tests, and visual evidence

**Explicitly not implemented (deferred):** Phase 17 graph-risk propagation, GNN, LLM analyst, automated containment.

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/models.py`, `packages/contracts-ts/src/models.ts` |
| ML training | `services/ml/src/aegis_ml/models/**`, `services/ml/src/aegis_ml/training/simulation_helpers.py` |
| ML inference | `services/ml/src/aegis_ml/inference/**` |
| ML evaluation | `services/ml/src/aegis_ml/evaluation/model_evaluation.py` |
| Incidents | `services/incidents/src/aegis_incidents/model_pipeline.py`, `model_promotion.py` |
| Persistence | `PostgresModelRepository` in `packages/persistence/.../postgres.py` |
| API | `apps/api/src/aegis_api/models/router.py`, `observability.py` |
| Scripts | `scripts/train_isolation_forest.py`, `evaluate_model.py`, `run_anomaly_detection.py` |
| Artifacts | `models/manifests/isolation-forest-v1/**`, `models/evaluation/isolation-forest/holdout-v1/**` |
| Tests | `tests/ml/models/**` |
| Docs | `docs/ml/anomaly-model.md`, ADR `0017-anomaly-model.md` |
| Demo | `apps/web/scripts/capture-anomaly-model-demo.mjs` |

## Files modified

| File | Reason |
|------|--------|
| `packages/contracts-python/src/aegis_contracts/entities.py` | Additive ModelManifestV1 + AlertV1 fields |
| `packages/contracts-*/versioning.*` | Phase 16 schema constants, `WORKSPACE_VERSION=0.0.0-phase16` |
| `services/ml/pyproject.toml` | sklearn, joblib, simulation-domain deps |
| `apps/api/src/aegis_api/main.py` | Register models routes |
| `apps/web/features/shell/components/inspector-panel.tsx` | Anomaly explanation UI |
| `apps/web/lib/realtime/event-projector.ts` | `model.score.` timeline prefix |
| `apps/web/features/live-run/live-run-provider.tsx` | Invalidate on model score events |
| `apps/web/fixtures/shell-dataset.json` | Isolation Forest fixture alert |
| `tests/contract/fixtures/compatibility-manifest.json` | Phase 16 hashes |

## Files removed

None.

## Contracts introduced or changed

| Contract | Version | Notes |
|----------|---------|-------|
| `AnomalyExplanationV1` | schema v1 | Structured model explanation |
| `TrainingRunManifestV1` | schema v1 | Training provenance |
| `ModelArtifactReferenceV1` | schema v1 | Artifact metadata |
| `ModelScoreRequestV1` / `ModelScoreResponseV1` | schema v1 | Scoring API |
| `ModelInferenceResultV1` | schema v1 | Score + dedup key |
| `ModelVerifyArtifactRequestV1` / `ResponseV1` | schema v1 | Verification API |
| `ModelManifestV1` | schema v1 | Additive optional training/threshold fields |
| `AlertV1` | schema v1 | Additive `anomalyExplanation`, `modelVersionId` |
| `WORKSPACE_VERSION` | `0.0.0-phase16` | Compatibility bump |

## Database migrations

None (uses existing `model_manifests`, `model_scores`, `stored_objects` tables).

## Environment and configuration changes

Uses existing `.env.example` PostgreSQL/Redis settings. No new required variables.

## Generated artifacts and fixtures

- `models/manifests/isolation-forest-v1/artifact.joblib`
- `models/manifests/isolation-forest-v1/manifest.json` — checksum `sha256:8007b09f1d331e9338c24dcd9e02c53b278afc09be5b3f4421665ae91ddbf185`
- `models/evaluation/isolation-forest/holdout-v1/evaluation_run.json`
- Screenshots: `/opt/cursor/artifacts/screenshots/16-*.png`

## Tests added

| Test | Proves |
|------|--------|
| `test_training_reproducibility.py` | Deterministic artifact checksum |
| `test_offline_online_parity.py` | Batch/single scorer agreement |
| `test_artifact_verification.py` | Corrupt/missing artifact rejection |
| `test_fallback.py` | Model outage → empty scores, no crash |
| `test_holdout_evaluation.py` | Training/holdout seed disjointness |
| `test_hidden_truth_leakage.py` | Evaluation labels not in runtime modules |
| `test_contracts.py` | Contract round-trip |

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run pytest -q` | **PASS** — 376 passed, 32 skipped |
| `uv run pytest tests/ml/models -q` | **PASS** — 11 passed |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `uv run python scripts/train_isolation_forest.py --steps 300` | **PASS** — 36 training vectors, threshold 0.752 |
| `uv run python scripts/evaluate_model.py --steps 300` | **PASS** — holdout metrics written |
| `pnpm --filter @aegis/web exec node scripts/capture-anomaly-model-demo.mjs` | **PASS** — 10 screenshots |

## Architecture decisions and ADRs

- **Created:** [0017-anomaly-model.md](../AEGIS-v1.0-Agent-Specs/adrs/0017-anomaly-model.md) (Status: **Proposed**)

## Known limitations

- Holdout entity-level recall depends on scenario entity mapping; current unsupervised model shows conservative detection on some seeds
- PostgreSQL persistence integration test skipped when database unavailable
- `mypy` not re-run — pre-existing API session path issue from Phase 14
- Phase 17 graph-risk propagation intentionally not implemented

## Deferred work

- Phase 17: graph-risk propagation (GNN)
- Production auto-retraining
- Boosted classifier / autoencoder

## Risks for dependent phases

- Preserve `FEATURE_SCHEMA_VERSION` 1 feature ordering
- Preserve model deduplication key format `{runId}:isolation-forest:{entityId}:{windowStartEpoch}`
- Phase 17 must not replace tabular scores; graph risk is additive
- Model scores remain advisory — no direct containment execution

## Acceptance criteria evidence

1. **Checked-in manifest reproduces model within tolerance:** `test_training_reproducibility.py`; manifest checksum `sha256:8007b09f...`; screenshot `16-manifest-checksum-validation.png`
2. **Offline and online scores agree:** `test_offline_online_parity.py`
3. **Artifact/schema mismatch fails closed:** `test_artifact_verification.py`; screenshot `16-corrupt-artifact-rejection.png`
4. **Rules continue during model outage:** `test_fallback.py`; screenshot `16-fallback-rules-only.png`

## Prohibited-shortcut confirmation

No GNN/graph-risk engine, no LLM-only explanations, no hidden-truth in training/inference runtime, no rules replacement, validation commands executed as recorded.
