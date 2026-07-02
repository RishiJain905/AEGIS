# ADR 0016: Rules and Statistical Baselines

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 15 must deliver transparent deterministic detectors and calibrated statistical baselines that consume Phase 14 `FeatureVectorV1` outputs, emit explainable `AlertCandidateV1` records, promote authoritative alerts through PostgreSQL, and evaluate on scenario-level holdouts. Hidden scenario truth must remain evaluation-only.

## Decision

1. **Contracts** live in `aegis_contracts.detection` / `@aegis/contracts-ts` detection module (`DetectionRuleV1`, `AlertCandidateV1`, `RuleExplanationV1`, `StatisticalBaselineV1`, `EvaluationRunV1`, `MetricReportV1`) at schema version 1.

2. **Additive `AlertV1` fields** (`confidence`, `detectorId`, `detectorVersion`, `ruleId`, `ruleVersion`, `explanation`, `evidence`, `deduplicationKey`) remain schema version 1 optional fields.

3. **Detection engine** in `services/incidents/` evaluates versioned rules against Phase 14 feature vectors only. No per-rule feature transforms.

4. **Statistical baselines** calibrate from training seeds `{1, 11, 1006}` only; holdout seeds `{1000, 1007, 1014}` are evaluation-only. Artifacts live under `models/baselines/v1/` with checksum manifests.

5. **Alert promotion** uses `PostgresAlertRepository` + `UnitOfWork.append_event(alert.created)` atomically. Deduplication key: `{runId}:{ruleId}:{entityId}:{windowStartEpoch}`.

6. **Realtime UI** invalidates TanStack Query `runs.alerts` on `alert.created` rather than extending `RunReplicatedState` in Phase 15.

7. **Phase 16 Isolation Forest** is explicitly out of scope; rules and baselines remain the production-path detectors for v1.0 Phase 15.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Extend `RunReplicatedState` with alerts array | Larger contract bump; query invalidation is sufficient for Phase 15 |
| Store baselines in PostgreSQL | Phase 14 pattern uses filesystem manifests; no new tables required |
| Per-rule feature transforms | Violates Phase 14 canonical feature pipeline contract |
| Random row evaluation split | Architecture requires scenario-level holdouts |

## Consequences

- Phases 16–17 must preserve rule IDs, deduplication keys, feature schema version 1 ordering, and alert promotion semantics.
- Changing threshold config requires version bump in `thresholds_v1.yaml` and registry version metadata.
- Evaluation harness may read `expected-evidence.yaml`; detection runtime modules must not.

## Approval

- [ ] Project owner
