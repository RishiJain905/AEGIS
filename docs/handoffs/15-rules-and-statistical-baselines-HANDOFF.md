# Phase 15 Handoff — Rules and Statistical Baselines

## Status

`READY FOR VALIDATION`

## Implemented

Phase 15 deliverables per `docs/AEGIS-v1.0-Agent-Specs/detection-and-machine-learning/15-rules-and-statistical-baselines.md`:

- Versioned detection contracts in `aegis_contracts.detection` / `@aegis/contracts-ts` detection module
- Additive `AlertV1` enrichment fields (confidence, detector metadata, structured explanation, evidence, deduplication key)
- Seven deterministic/statistical detectors in `services/incidents/rules/`
- Statistical baseline calibration/scoring in `services/ml/baselines/`
- Detection pipeline with dedup, cooldown, suppression in `services/incidents/pipeline.py`
- `PostgresAlertRepository` + atomic `alert.created` promotion via `UnitOfWork.append_event`
- API routes: detection registry/baselines/evaluate, alerts list/detail
- Scripts: `calibrate_baselines.py`, `run_detection.py`, `evaluate_rules.py`
- UI: inspector alert detail, live query invalidation on `alert.created`, `/detection/observability`
- Documentation: `docs/ml/rule-baselines.md`, ADR `0016-rules-and-statistical-baselines.md`

**Explicitly not implemented (deferred):** Phase 16 Isolation Forest, Phase 17 graph-risk, incident correlation.

## Files added

| Area        | Key paths                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------ |
| Contracts   | `packages/contracts-python/src/aegis_contracts/detection.py`, `packages/contracts-ts/src/detection.ts` |
| Rules       | `services/incidents/src/aegis_incidents/rules/**`                                                      |
| Baselines   | `services/ml/src/aegis_ml/baselines/**`                                                                |
| Pipeline    | `services/incidents/src/aegis_incidents/pipeline.py`, `promotion.py`, `evaluation.py`                  |
| Persistence | `PostgresAlertRepository` in `packages/persistence/.../postgres.py`                                    |
| API         | `apps/api/src/aegis_api/detection/**`                                                                  |
| Scripts     | `scripts/calibrate_baselines.py`, `run_detection.py`, `evaluate_rules.py`                              |
| Tests       | `tests/ml/rules/**`, `tests/integration/detection/**`                                                  |
| Artifacts   | `models/baselines/v1/**`, `models/evaluation/rules/holdout-v1/**`                                      |
| Docs        | `docs/ml/rule-baselines.md`, ADR 0016, `apps/web/scripts/capture-detection-demo.mjs`                   |

## Files modified

| File                                                           | Reason                                                        |
| -------------------------------------------------------------- | ------------------------------------------------------------- |
| `packages/contracts-python/src/aegis_contracts/entities.py`    | Additive `AlertV1` fields                                     |
| `packages/contracts-ts/src/entities.ts`                        | TS alert schema parity                                        |
| `packages/contracts-*/versioning.*`                            | `WORKSPACE_VERSION=0.0.0-phase15`, detection schema constants |
| `packages/persistence/**`                                      | Alert repository + UoW wiring                                 |
| `apps/api/src/aegis_api/runs/router.py`                        | Real alert/incident list endpoints                            |
| `apps/web/features/shell/components/inspector-panel.tsx`       | Alert explanation UI                                          |
| `apps/web/features/live-run/live-run-provider.tsx`             | Invalidate alerts on `alert.created`                          |
| `apps/web/fixtures/shell-dataset.json`                         | Enriched fixture alerts                                       |
| `tests/contract/fixtures/compatibility-manifest.json`          | Phase 15 workspace + schema hashes                            |
| `services/incidents/pyproject.toml`, `apps/api/pyproject.toml` | Package wiring                                                |

## Contracts introduced or changed

| Contract                             | Version         | Notes                                   |
| ------------------------------------ | --------------- | --------------------------------------- |
| `DetectionRuleV1` / registry         | schema v1       | Seven rules, versioned thresholds       |
| `AlertCandidateV1`                   | schema v1       | Observed/baseline/threshold/explanation |
| `RuleExplanationV1`                  | schema v1       | Structured only                         |
| `StatisticalBaselineV1` / manifest   | schema v1       | Training-seed calibration               |
| `EvaluationRunV1` / `MetricReportV1` | schema v1       | Holdout evaluation                      |
| `AlertV1`                            | schema v1       | Additive optional detection fields      |
| `WORKSPACE_VERSION`                  | `0.0.0-phase15` | Compatibility bump                      |

## Database migrations

None (deduplication keys stored in alert JSONB payload; no new tables).

## Environment and configuration changes

None required beyond existing PostgreSQL/Redis stack.

## Generated artifacts and fixtures

- `models/baselines/v1/baseline.json` + `manifest.json`
- `models/evaluation/rules/holdout-v1/evaluation_run.json`
- Screenshots: `/opt/cursor/artifacts/screenshots/15-*.png`

## Tests added

| Test                            | Proves                                     |
| ------------------------------- | ------------------------------------------ |
| `test_rule_registry.py`         | Seven versioned rules                      |
| `test_deterministic_rules.py`   | Conditional firing                         |
| `test_baselines.py`             | Deterministic calibration + z-score        |
| `test_dedup_suppression.py`     | Dedup key stability                        |
| `test_pipeline_isolation.py`    | Rule failures isolated                     |
| `test_determinism.py`           | Identical checksum on repeat               |
| `test_hidden_truth_leakage.py`  | No expected-evidence in runtime modules    |
| `test_evaluation_holdout.py`    | Disjoint train/holdout seeds               |
| `test_detection_persistence.py` | PG alert + event path (skipped without PG) |

## Commands executed and results

| Command                                                                 | Result                                                     |
| ----------------------------------------------------------------------- | ---------------------------------------------------------- |
| `uv run ruff check .`                                                   | PASS (after `--fix` on new modules)                        |
| `uv run mypy apps services packages`                                    | Not re-run — pre-existing session path issue from Phase 14 |
| `uv run pytest -q`                                                      | **PASS** — 341 passed, 32 skipped                          |
| `uv run pytest tests/ml/rules -q`                                       | **PASS** — 14 passed                                       |
| `pnpm check-contracts`                                                  | **PASS**                                                   |
| `pnpm typecheck`                                                        | **PASS**                                                   |
| `uv run python scripts/calibrate_baselines.py`                          | **PASS**                                                   |
| `uv run python scripts/evaluate_rules.py`                               | **PASS** — metrics artifact written                        |
| `pnpm --filter @aegis/web exec node scripts/capture-detection-demo.mjs` | **PASS** — 9 screenshots                                   |

### Stack startup (fixture demo)

```bash
uv run python scripts/calibrate_baselines.py
uv run aegis-api
pnpm --filter @aegis/web dev
pnpm --filter @aegis/web exec node scripts/capture-detection-demo.mjs
```

### Stack startup (live PG path)

```bash
sudo service postgresql start && sudo service redis-server start
uv run alembic upgrade head
uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 300
uv run python scripts/run_detection.py --run-id <run_id>
uv run aegis-worker --mode outbox-relay
```

## Architecture decisions and ADRs

- **Created:** [0016-rules-and-statistical-baselines.md](../AEGIS-v1.0-Agent-Specs/adrs/0016-rules-and-statistical-baselines.md) (Status: **Proposed**)

## Known limitations

- Holdout evaluation metrics are scenario-dependent; some seeds show partial rule coverage in the current threshold tuning
- Integration persistence test skipped when PostgreSQL unavailable
- Screenshot demo uses fixture mode when live PG stack not running
- `mypy` blocked by pre-existing API session module path issue

## Deferred work

- Phase 16: Isolation Forest model training/inference
- Phase 17: graph-risk propagation
- Incident correlation engine

## Risks for dependent phases

- Preserve `FEATURE_SCHEMA_VERSION` 1 feature ordering
- Preserve deduplication key format and `alert.created` payload shape
- Phase 16 must not bypass rules; architecture specifies graceful fallback to rules only after model path exists

## Acceptance criteria evidence

1. **Baseline detectors cover intended signal families:** seven rules in registry; `test_rule_registry.py`; screenshot `15-statistical-baseline-alert.png`
2. **Every firing explainable:** `RuleExplanationV1` on all candidates; screenshot `15-alert-detail-explanation.png`
3. **Evaluation uses held-out runs/seeds:** `evaluate_rules.py` + `test_evaluation_holdout.py`; screenshot `15-evaluation-metrics.png`
4. **Rule failures isolated:** `test_pipeline_isolation.py`

## Prohibited-shortcut confirmation

No Isolation Forest, no per-rule feature transforms, no hidden-truth in detection runtime, no scaffolding-only handlers, validation commands executed as recorded.
