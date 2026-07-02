# Phase 14 Handoff — Feature Pipeline

## Status

`READY FOR VALIDATION`

## Implemented

Phase 14 deliverables per `docs/AEGIS-v1.0-Agent-Specs/detection-and-machine-learning/14-feature-pipeline.md`:

- Versioned feature contracts in `aegis_contracts.features` / `@aegis/contracts-ts` (`FeatureSchemaManifestV1`, `FeatureVectorV1`, `FeatureWindowV1`, `FeatureProvenanceV1`, `DatasetManifestV1`, `OnlineFeatureUpdateV1`, compute/parity API contracts)
- Shared deterministic transform engine in `services/ml/src/aegis_ml/features/` with simulation-time tumbling windows (300s), eight telemetry categories, hidden-truth guard, duplicate/late-event rejection
- Offline dataset export: `scripts/build_feature_dataset.py` → `models/datasets/<run-id>/features.jsonl` + `manifest.json` with `sha256:` checksum
- Online API: `GET /api/v1/features/schema`, `POST /api/v1/features/compute`, `POST /api/v1/features/parity-check`
- Diagnostic UI: `GET /features/observability`
- Documentation: `docs/ml/feature-pipeline.md`, ADR `0015-feature-pipeline.md`
- Evidence renderer: `scripts/render_feature_pipeline_evidence.py`, capture script `apps/web/scripts/capture-feature-pipeline-demo.mjs`

**Explicitly not implemented (deferred):** Phase 15 detection rules, Phase 16 anomaly models, Phase 17 graph-risk propagation, classifiers, alert generators.

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/features.py`, `packages/contracts-ts/src/features.ts` |
| ML engine | `services/ml/src/aegis_ml/features/**` |
| API | `apps/api/src/aegis_api/features/**` |
| Scripts | `scripts/build_feature_dataset.py`, `scripts/render_feature_pipeline_evidence.py` |
| Tests | `tests/ml/features/**` |
| Fixtures | `tests/contract/fixtures/valid/feature_*`, `dataset_manifest_v1.json`, generated schemas |
| Docs | `docs/ml/feature-pipeline.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0015-feature-pipeline.md`, `models/datasets/README.md` |
| Demo | `apps/web/scripts/capture-feature-pipeline-demo.mjs` |

## Files modified

| File | Reason |
|------|--------|
| `packages/contracts-python/src/aegis_contracts/{versioning,__init__,fixtures}.py` | Phase 14 schema versions, exports, fixture map |
| `packages/contracts-ts/src/{versioning,index}.ts` | TS parity |
| `services/ml/pyproject.toml`, `apps/api/pyproject.toml`, `apps/api/src/aegis_api/main.py` | Wire ML service and routes |
| `tests/contract/fixtures/compatibility-manifest.json` | New artifact hashes, workspace `0.0.0-phase14` |
| `tests/__init__.py`, `tests/ml/**/__init__.py` | Test package imports |

## Files removed

None.

## Contracts introduced or changed

| Contract | Version | Description |
|----------|---------|-------------|
| `FeatureSchemaManifestV1` | schema v1 | 27 ordered features, units, missing sentinel, categorical map v1 |
| `FeatureVectorV1` | schema v1 | Window output + provenance |
| `FeatureWindowV1` | schema v1 | Window metadata and watermark |
| `FeatureProvenanceV1` | schema v1 | Run/entity/sequence/sim-time bounds |
| `DatasetManifestV1` | schema v1 | Content-addressed dataset export |
| `OnlineFeatureUpdateV1` | schema v1 | Incremental online emission |
| `FeatureComputeRequestV1` / `FeatureComputeResponseV1` | schema v1 | Online compute API |
| `FeatureParityCheckResponseV1` | schema v1 | Offline/online checksum parity |
| `WORKSPACE_VERSION` | `0.0.0-phase14` | Workspace parity bump |

## Database migrations

None (datasets are filesystem artifacts; events read from existing `domain_events`).

## Environment and configuration changes

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEGIS_FEATURE_BATCH_SIZE` | `1000` | Documented batch size for large reads |

## Generated artifacts and fixtures

- Golden fixtures: `tests/contract/fixtures/valid/feature_*`, `dataset_manifest_v1.json`, `online_feature_update_v1.json`
- Generated schemas for all new contracts
- Screenshots: `/opt/cursor/artifacts/screenshots/14-*.png`
- Evidence HTML: `/opt/cursor/artifacts/feature-pipeline-evidence.html`

## Tests added

| Test | Proves |
|------|--------|
| `test_schema_registry.py` | Stable 27-feature ordering and missing sentinel |
| `test_window_semantics.py` | Simulation-time tumbling windows |
| `test_aggregators.py` | Per-category numeric correctness and protocol one-hot |
| `test_input_guard.py` | Hidden truth / unsupported / malformed rejection |
| `test_ordering.py` | Duplicate and out-of-order detection |
| `test_determinism.py` | Identical checksum on repeat |
| `test_offline_online_parity.py` | Shared engine parity |
| `test_hidden_truth_leakage.py` | Hidden events never in feature values |
| `test_dataset_manifest.py` | Deterministic `sha256:` dataset manifest |
| `test_performance_batch.py` | 5000-event batch under time bound |
| `test_contracts.py` | Contract round-trip |

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run mypy apps services packages` | **BLOCKED** — pre-existing `aegis_api.db.session` duplicate module path |
| `uv run pytest -q` | **PASS** — 317 passed, 31 skipped |
| `uv run pytest tests/ml/features -q` | **PASS** — 21 passed |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm test` | **PASS** |
| `uv run aegis-simulator run --scenario scenarios/operation-silent-relay --seed 1000 --steps 120` | **PASS** |
| `uv run python scripts/render_feature_pipeline_evidence.py` | **PASS** |
| `pnpm --filter @aegis/web exec node scripts/capture-feature-pipeline-demo.mjs` | **PASS** — 8 screenshots |
| `uv run alembic upgrade head` | **BLOCKED** — PostgreSQL unavailable in validation VM |
| `uv run aegis-simulator run-persisted` / `build_feature_dataset.py` | **BLOCKED** — requires PostgreSQL |

### Stack startup (when PostgreSQL available)

```bash
sudo service postgresql start && sudo service redis-server start
uv run alembic upgrade head
uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 200
uv run python scripts/build_feature_dataset.py --run-id <run_id>
uv run aegis-api
NEXT_PUBLIC_AEGIS_DATA_SOURCE=api pnpm --filter @aegis/web dev
pnpm --filter @aegis/web exec node scripts/capture-feature-pipeline-demo.mjs
```

## Architecture decisions and ADRs

- **Created:** [0015-feature-pipeline.md](../AEGIS-v1.0-Agent-Specs/adrs/0015-feature-pipeline.md) (Status: **Proposed**)
- **Unchanged:** ADRs 0001–0014 except documented PG-authoritative alignment with ADR 0014

## Known limitations

- PostgreSQL unavailable in validation VM; persisted-run dataset CLI and integration API tests skipped
- `mypy` blocked by pre-existing API session module path issue
- Command-centre screenshot captured in fixture mode; live PG-backed run capture requires database services
- Feature evidence HTML uses Operation Silent Relay simulation engine events (same telemetry contracts as persisted runs)

## Deferred work

- Phase 15: rule registry and statistical baselines
- Phase 16: Isolation Forest / model training
- Phase 17: graph-risk propagation
- Optional: persist feature vectors to PostgreSQL (not required by Phase 14 spec)

## Risks for dependent phases

- Phases 15–17 must preserve `FEATURE_SCHEMA_VERSION` 1 feature ordering and provenance fields
- Do not import hidden scenario manifests into feature transforms
- Model manifests must record `featureSchemaVersion` when scoring (Phase 01 contract)

## Acceptance criteria evidence

1. **Offline and online features match for identical events:** `test_offline_online_parity.py`; evidence HTML `parity.matching=true`; screenshot `14-offline-online-parity.png`; checksum `sha256:d982e7f8038d5ef4a7b6eedc6fb1fdc6ed1884168fb66872d8ecb1d17c251ec7`
2. **Every vector has schema version and provenance:** `FeatureVectorV1` contract; `test_contracts.py`; screenshot `14-feature-window-row.png`
3. **Hidden truth absent from inference inputs:** `test_hidden_truth_leakage.py`, `test_input_guard.py`; rejections screenshot `14-invalid-input-handling.png`
4. **Dataset builds deterministic and checksummed:** `test_dataset_manifest.py`; evidence `dataset.datasetChecksum`; screenshot `14-dataset-metadata.png`

## Prohibited-shortcut confirmation

No scaffolding-only handlers, no separate offline/online transforms, no hidden-truth in features, no Phase 15/16 detection/model demo code, no skipped weakening of prior tests, validation commands executed as recorded above.
