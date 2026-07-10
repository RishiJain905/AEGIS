# ADR 0030: Scoring and After-Action Experience

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 29 requires deterministic, explainable run scoring and an after-action learning experience. Architecture keeps PostgreSQL authoritative, forbids opaque model grading as world truth, and already defines `ModelScore` for ML detection/risk inference. The Phase 29 specification lists `packages/scoring-contracts/**`, but ADR 0002 requires durable cross-language contracts to live in the shared contracts packages (the same adjustment used for reports, replay, and cinematic contracts).

## Decision

1. **Shared contract home:** Durable scoring contracts (`ScoreRubricV1`, `ScoreComponentV1`, `ScoreExplanationV1`, `ScoreProvenanceV1`, `DecisionReviewV1`, `MissedEvidenceItemV1`, `ValidAlternativeV1`, `RunScoreV1`, `AfterActionViewModelV1`, `RunComparisonV1`, `ScoreExportArtifactV1`) live in `packages/contracts-ts` and `packages/contracts-python` with schemaVersion 1 and compatibility fixtures. Domain logic lives in `services/scoring/**`. UI lives in `apps/web/features/after-action/**`.

2. **`RunScore` ≠ `ModelScore`:** Run grading is pedagogical post-completion scoring derived from scenario rubrics and authoritative run facts. ML `ModelScore` remains entity-level detection/risk inference and must not be reused as the run grade.

3. **`RunComparison` ≠ `ReplayComparisonV1`:** Phase 29 `RunComparisonV1` compares repeated-run scores. Phase 26 `ReplayComparisonV1` remains a single-run two-cursor state diff.

4. **Deterministic scoring authority:** Numeric scores, grades, penalties, bonuses, and pass/fail results are computed only by versioned grading rules (`GRADING_ENGINE_VERSION`) against scenario rubric criteria, expected-evidence, and PostgreSQL-persisted events/evidence/decisions/outcomes. Optional coaching prose is non-authoritative and clearly labelled.

5. **Historical-time evaluation:** Operator decision reviews use only information available at or before the decision’s sequence/sim-time. Future knowledge must not inflate or deflate decision scores.

6. **Counterfactuals are labelled alternatives:** Valid alternative / counterfactual paths are stored as `ValidAlternativeV1` with `authoritative: false` and must never be presented as facts of the completed run or merged into authoritative component scores.

7. **Idempotent persistence:** Scoring writes only to `run_scores` (and optional export artifacts). Duplicate requests with the same input fingerprint return the existing authoritative result. Scoring never mutates domain events, evidence, agent outputs, approvals, reports, or replay snapshots.

8. **Hidden-cause disclosure:** Hidden cause labels may be revealed only after run completion in the after-action experience. Live play and cinematic presentation remain concealed.

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| Separate `packages/scoring-contracts` package | Conflicts with ADR 0002 single shared-contract home |
| LLM as authoritative grader | Forbidden by architecture and Phase 29; non-deterministic and unexplainable |
| Reuse `ModelScore` for run grades | Different semantics; conflates ML inference with pedagogical scoring |
| Client-only scoring | Violates PostgreSQL authority and reproducibility after restart |
| Present counterfactuals as run facts | Violates after-action truthfulness requirements |

## Consequences

- Phase 29 adds shared scoring contracts, a scoring service, persistence, API routes, and an after-action dashboard without competing report or replay engines.
- Dependent production-readiness phases (30–34) must preserve deterministic grading, provenance, idempotency, and the distinction between authoritative scores and coaching/counterfactuals.
- Silent Relay content remains in `scenarios/`; platform scoring code stays scenario-agnostic and rubric-driven.

## Security and reliability

- Incomplete, incompatible, or tampered grading inputs fail closed with structured error codes.
- Integrity checksums and version metadata are recorded on every authoritative `RunScore`.
- No offensive capability introduced.
- No architecture non-negotiable rules are changed.

## Approval

- [ ] Project owner
