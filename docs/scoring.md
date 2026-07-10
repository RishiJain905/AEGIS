# Scoring and After-Action Experience

Phase 29 implements deterministic, explainable run scoring and the after-action learning experience.

## Authority

- Numeric scores, grades, penalties, bonuses, and pass/fail results are computed only by the versioned grading engine (`GRADING_ENGINE_VERSION = 1.0.0-phase29`) against scenario rubric criteria, expected-evidence, and PostgreSQL-persisted run facts.
- Optional coaching prose is non-authoritative and labelled as such.
- Counterfactual / valid alternatives are labelled non-authoritative and are never merged into authoritative component scores.
- `RunScore` is distinct from ML `ModelScore`.
- `RunComparison` (multi-run score comparison) is distinct from `ReplayComparisonV1` (single-run cursor diff).

## Packages

| Area | Path |
|------|------|
| Contracts | `packages/contracts-ts/src/scoring.ts`, `packages/contracts-python/src/aegis_contracts/scoring.py` |
| Engine | `services/scoring/` |
| Persistence | `run_scores` table (migration `012_run_scores`) |
| API | `apps/api/src/aegis_api/scoring/router.py` |
| UI | `apps/web/features/after-action/` |
| Docs/ADR | `docs/scoring.md`, ADR 0030 |

## Score categories

Silent Relay (and any scenario with a `scoring` section) uses eight weighted criteria:

1. Detection speed
2. Evidence coverage
3. Hypothesis quality
4. False-positive cost
5. Response proportionality
6. Service impact
7. Recurrence handling
8. Objectives completion

Overall score = Σ(rawScore × weight × maxScore), clamped to `[0, maxScore]`.

Grade bands: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, else F. Pass threshold = 60.

## Provenance

Every `RunScore` records:

- scenario version, rubric version, grading-engine version
- input event sequence range
- input checksum and integrity checksum
- fingerprint (idempotency key)
- calculation timestamp

Duplicate scoring requests with the same fingerprint return the existing authoritative result.

## Historical-time decisions

`DecisionReviewV1` entries evaluate approvals/rejections/modifications using only events and evidence available at or before the decision sequence. `usedFutureKnowledge` is always `false`.

## Counterfactuals

`ValidAlternativeV1` entries project evidence-grounded alternative response branches. They set `authoritative: false` and must be presented as alternatives/simulations, not completed-run facts.

## API

- `POST /api/v1/runs/{run_id}/score`
- `GET /api/v1/runs/{run_id}/score`
- `GET /api/v1/runs/{run_id}/after-action`
- `GET /api/v1/runs/{run_id}/score/export/{json|markdown}`
- `GET /api/v1/runs/score-comparison?left=&right=`

## Failure modes

Incomplete runs, missing rubrics, incompatible grading engines, and tampered/mismatched inputs fail closed with structured `ScoreErrorCode` values. Scoring never mutates domain events, evidence, approvals, reports, or replay snapshots.

## UI

Route: `/after-action/[runId]`

Panels: overall score/grade, category breakdowns, rule-linked explanations, timeline/decisions, missed evidence, labelled alternatives, SCRIBE integration, export metadata, coaching (non-authoritative), replay jumps.

## Deferred (Phases 30–34)

Production authentication, observability hardening, security hardening, cloud deployment, and full-system validation remain out of scope for Phase 29.
