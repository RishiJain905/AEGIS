# ADR 0017: Isolation Forest Anomaly Model (Phase 16)

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 16 must train, version, evaluate, store, load, and serve an Isolation Forest anomaly detector that consumes Phase 14 feature vectors, compares against Phase 15 rules/baselines, and emits advisory `ModelScoreV1` records without bypassing human approval workflows.

## Decision

1. **Algorithm:** scikit-learn `IsolationForest` in a `StandardScaler` + model `Pipeline` with fixed `random_state=42`, persisted as joblib under `models/manifests/isolation-forest-v1/`.

2. **Contracts:** Phase 16 model contracts live in `aegis_contracts.models` (`AnomalyExplanationV1`, `TrainingRunManifestV1`, `ModelArtifactReferenceV1`, scoring API contracts). `ModelManifestV1` and `AlertV1` receive additive optional fields at schema version 1.

3. **Training/evaluation splits:** Reuse Phase 15 seed policy — training seeds `{1, 11, 1006}`, holdout `{1000, 1007, 1014}`. Hidden root-cause labels remain evaluation-only in `aegis_ml.evaluation.model_evaluation`.

4. **Score semantics:** sklearn `decision_function` is negated and min-max scaled to `[0, 1]` using training bounds; higher score = more anomalous. Threshold calibrated at `(1 - contamination)` percentile on training scores.

5. **Artifact policy:** Manifest checksum verification is mandatory before load. Corrupt, missing, incompatible, or rejected artifacts fail closed. Approved artifact path is filesystem-first (matching Phase 15 baseline pattern) with optional PostgreSQL metadata via `PostgresModelRepository`.

6. **Detection integration:** Rules pipeline always runs. Model inference runs in parallel via `model_pipeline.py`. Model failure sets `fallbackActive` and does not block rules. Model anomalies above threshold promote `AlertV1` with `detectorId: isolation-forest` and structured `anomalyExplanation`.

7. **Realtime:** `model.score.recorded` events emitted alongside `alert.created` for threshold breaches; UI invalidates alert queries on both prefixes.

8. **Phase 17 boundary:** Graph-risk propagation and GNN scoring are explicitly out of scope. Phase 16 scores are tabular entity/window anomalies only.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Replace rules with model-only detection | Violates architecture baseline order and Phase 15 handoff |
| Hidden-truth labels in training | Violates evaluation-only hidden scenario truth rule |
| PostgreSQL-only artifact storage | Phase 14/15 filesystem manifest pattern is established |
| LLM-generated explanations | Architecture requires structured explanations, not prose-only |

## Consequences

- Phase 17 must preserve model manifest IDs, deduplication keys, feature schema version 1, and advisory-only score semantics.
- Model artifact updates require new semantic version + manifest checksum bump.
- Rollback: prior manifest remains addressable via `predecessorModelId` field.

## Approval

- [ ] Project owner
