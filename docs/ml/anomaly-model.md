# Anomaly Model (Phase 16)

## Overview

Phase 16 delivers a versioned Isolation Forest anomaly detector trained on Operation Silent Relay feature vectors from the Phase 14 pipeline. Scores are advisory, explainable, and persisted through the existing alert/realtime path. Phase 15 rules and statistical baselines remain active and provide fallback when the model is unavailable.

## Training data

| Item | Value |
|------|-------|
| Scenario | `scenarios/operation-silent-relay` |
| Training seeds | `1`, `11`, `1006` |
| Holdout seeds | `1000`, `1007`, `1014` (evaluation only) |
| Feature schema | version `1`, 27 ordered features |
| Steps per seed | `300` (simulation-time windows) |
| Leakage protection | Hidden root-cause mapping only in `aegis_ml.evaluation.model_evaluation` |

## Model configuration

| Hyperparameter | Value |
|----------------|-------|
| Algorithm | `IsolationForest` |
| `n_estimators` | `100` |
| `contamination` | `0.05` |
| `random_state` | `42` |
| Preprocessing | `StandardScaler` (fit on training only) |
| sklearn version | recorded in manifest |

## Score semantics

- Raw sklearn `decision_function` → negated → min-max scaled to `[0, 1]` using training-set bounds.
- **Higher score = more anomalous.**
- Threshold: `(1 - contamination)` percentile on normalized training scores.
- Risk bands: `normal`, `elevated`, `high` (from calibrated elevated/high thresholds).

## Artifacts

```
models/manifests/isolation-forest-v1/
  artifact.joblib      # pipeline + calibration + feature stats
  manifest.json        # ModelManifestV1
  training_run.json    # TrainingRunManifestV1
```

Checksum verification is required before load. See `scripts/train_isolation_forest.py` and `POST /api/v1/models/verify-artifact`.

## Commands

```bash
uv run python scripts/train_isolation_forest.py --steps 300
uv run python scripts/evaluate_model.py --steps 300
uv run python scripts/run_anomaly_detection.py --run-id <run_id>
uv run pytest tests/ml/models -q
```

## Fallback behavior

When the artifact is missing, corrupt, or schema-incompatible, inference returns `fallbackActive: true` with empty scores. The Phase 15 rules pipeline continues unaffected.

## Phase 17 boundary

Graph-risk propagation (GNN) is deferred. Phase 16 scores are per-entity/window tabular anomalies only.
