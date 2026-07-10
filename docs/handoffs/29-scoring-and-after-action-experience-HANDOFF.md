# Phase 29 Handoff — Scoring and After-Action Experience

## Status

`READY FOR REVIEW`

## Implemented

Mapped to Phase 29 spec Sections 7 and 18:

| Spec item | Implementation |
| --------- | -------------- |
| Rubric-versioned scoring for 8 categories | `services/scoring` criterion calculators + Silent Relay manifest rubric |
| Numeric scores deterministic, separate from coaching | `compute_run_score`; `coachingAuthoritative: false` |
| Score provenance | `ScoreProvenanceV1` with scenario/rubric/engine versions, event range, checksums, fingerprint |
| After-action dashboard | `apps/web/features/after-action/**`, route `/after-action/[runId]` |
| Link feedback to replay | Jump-to-replay links with sequence query |
| Reveal hidden cause after completion | `hiddenCauseRevealed` only on completed scored runs |
| SCRIBE integration + run comparison | After-action view links SCRIBE; `RunComparisonV1` API |
| **AC1** Golden branches → reproducible attributed scores | `tests/scoring/test_scoring_engine.py`, acceptance tests |
| **AC2** Alternative valid responses can score well | Contain vs remediate/investigate branches + labelled alternatives |
| **AC3** Every component explainable from source records | Rule IDs + event/evidence citations on each component |
| **AC4** After-action teaches what happened and why | Dashboard: timeline, decisions, missed evidence, alternatives, lessons |

**Explicitly not implemented:** Phase 30 auth, Phase 31 observability, Phase 32 security hardening, cloud deployment, leaderboards, opaque LLM grading.

**Contract packaging note:** Spec listed `packages/scoring-contracts/**`. Per ADR 0002 / ADR 0030 (same adjustment as Phases 23/25/28), durable contracts live in shared `packages/contracts-ts` + `packages/contracts-python`.

## Files added

| Path | Reason |
| ---- | ------ |
| `packages/contracts-ts/src/scoring.ts` | Durable scoring contracts |
| `packages/contracts-python/src/aegis_contracts/scoring.py` | Python mirror |
| `services/scoring/**` | Deterministic scoring engine + service |
| `apps/api/src/aegis_api/scoring/**` | Thin FastAPI routes |
| `apps/web/features/after-action/**` | After-action dashboard UI |
| `apps/web/src/app/(shell)/after-action/[runId]/page.tsx` | Route |
| `apps/web/fixtures/after-action-fixture.*` | Fixture-mode demo data |
| `migrations/versions/012_run_scores.py` | `run_scores` persistence |
| `packages/persistence/.../repositories/scoring.py` | Score repository |
| `tests/scoring/**` | Engine + acceptance tests |
| `tests/unit/after-action/acceptance.test.ts` | AC1–AC4 frontend mapping |
| `tests/e2e/after-action.spec.ts` | Playwright coverage |
| `tests/contract/fixtures/valid/*score*` + schemas | Compatibility fixtures |
| `docs/scoring.md` | Operator/architecture notes |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0030-scoring-and-after-action.md` | ADR |
| `apps/web/scripts/capture-after-action-demo.mjs` | Visual evidence harness |
| `docs/handoffs/evidence/29-scoring-and-after-action/*` | Screenshots + recording |
| `docs/handoffs/29-scoring-and-after-action-experience-HANDOFF.md` | This handoff |

## Files modified

| Path | Reason |
| ---- | ------ |
| `packages/contracts-*/src/versioning.*` | Schema versions + `WORKSPACE_VERSION=0.0.0-phase29` |
| `packages/contracts-*/src/index` / fixtures / `__init__` | Export scoring contracts |
| `packages/persistence` UoW + ORM tables | `run_scores` wiring |
| `apps/api` main + pyproject | Mount scoring router; depend on `aegis-scoring` |
| `apps/web` API client, nav, vitest config | After-action client + nav entry |
| `pyproject.toml` / `package.json` | Workspace member + mypy/import-linter |
| `docs/scenarios/silent-relay.md` | Runtime scoring now live |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/README.md` | Point to ADR 0030 |
| `tests/contract/fixtures/compatibility-manifest.json` | New artifact hashes |

## Files removed

None.

## Contracts introduced or changed

Durable cross-language (schemaVersion 1):

- `ScoreExplanationV1`, `ScoreRubricV1`, `ScoreComponentV1`, `ScoreProvenanceV1`
- `DecisionReviewV1`, `MissedEvidenceItemV1`, `ValidAlternativeV1`
- `RunScoreV1`, `AfterActionViewModelV1`, `RunComparisonV1`, `ScoreExportArtifactV1`
- `GRADING_ENGINE_VERSION = 1.0.0-phase29`

`WORKSPACE_VERSION` bumped to `0.0.0-phase29`.

## Database migrations

- `012_run_scores` — `run_scores` table with unique fingerprint for idempotent authoritative results.

## Environment and configuration changes

None required. Fixture mode uses existing `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture`.

## Generated artifacts and fixtures

- Contract fixtures/schemas under `tests/contract/fixtures/`
- Visual evidence under `docs/handoffs/evidence/29-scoring-and-after-action/`

## Tests added

| Test | Proves |
| ---- | ------ |
| `tests/scoring/test_scoring_engine.py` | Determinism, alternatives, explainability, incomplete fail-closed, restraint credit |
| `tests/scoring/test_scoring_acceptance.py` | AC1–AC4 + export metadata |
| `tests/unit/after-action/acceptance.test.ts` | Frontend AC1–AC4 |
| `tests/e2e/after-action.spec.ts` | Dashboard, alternatives, replay jump, error, narrow, keyboard |

## Validation commands and results

| Command | Result |
| ------- | ------ |
| `pnpm format:check` | PASS |
| `pnpm lint` | PASS |
| `pnpm typecheck` | PASS |
| `pnpm test` | PASS |
| `pnpm build` | PASS (includes `/after-action/[runId]`) |
| `pnpm check-contracts` | PASS |
| `pnpm boundaries` | PASS (via lint) |
| `uv run ruff check .` | PASS |
| `pnpm typecheck:py` (includes `aegis_scoring`) | PASS |
| `uv run pytest -q` | PASS (837 passed, 52 skipped) |
| `uv run pytest tests/scoring -q` | PASS (9 passed) |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web test:e2e -- tests/e2e/after-action.spec.ts` | PASS (6 passed) |
| `uv run lint-imports` | PASS |

### Demo / visual evidence commands

```bash
export NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture
pnpm --filter @aegis/web dev --port 3000
# then:
SCREENSHOT_BASE_URL=http://127.0.0.1:3000 node apps/web/scripts/capture-after-action-demo.mjs
```

Scoring reproducibility smoke (engine-only):

```bash
uv run pytest tests/scoring/test_scoring_engine.py::test_golden_branch_reproducible_attributed_scores -q
```

## Architecture decisions and ADR references

- ADR 0030 — Scoring and After-Action Experience (new)
- ADR 0002 — shared contract home (followed)
- ADR 0024 — SCRIBE consumed, not redefined
- ADR 0026/0027 — replay reconstruction/bookmarks consumed for jumps
- ADR 0029 — cinematic is not scoring authority; hidden cause revealed only post-completion

## Known limitations and deferred work

- Full stack scoring against a live persisted Silent Relay run requires API + Postgres + completed investigation artifacts; fixture mode demonstrates the UX and contracts.
- Production auth/authorization (Phase 30), observability (Phase 31), security hardening (Phase 32), and deployment remain deferred.
- Optional coaching text is template/static non-authoritative prose (no LLM as scoring authority).

## Risks and instructions for dependent phases

- Preserve deterministic grading, provenance checksums, and idempotent fingerprints.
- Do not present counterfactuals as completed-run facts.
- Do not conflate `RunScore` with `ModelScore` or `RunComparison` with `ReplayComparisonV1`.
- Keep platform scoring scenario-agnostic; scenario content stays under `scenarios/`.

## Evidence for every acceptance criterion

| AC | Evidence |
| -- | -------- |
| AC1 | `test_golden_branch_reproducible_attributed_scores`; identical fingerprint/overall on re-score; provenance versions present in UI screenshot `29-overall-score-and-grade.png` |
| AC2 | `test_alternative_valid_response_can_score_well`; screenshot `29-valid-alternatives-counterfactual.png` shows labelled non-authoritative alternative |
| AC3 | Component explanations with rule IDs; screenshot `29-score-explanation-rule-ids.png` |
| AC4 | Timeline, decisions, missed evidence, lessons, SCRIBE link; screenshots `29-timeline-review-decisions.png`, `29-missed-evidence.png`, `29-scribe-integration.png`; recording `29-after-action-navigation.webm` |

## Confirmation: no prohibited shortcut used

Production paths implement real scoring logic and persistence. No Silent Relay hard-codes in platform packages (scenario content remains under `scenarios/`). No LLM authoritative grading. No mutation of historical run/replay/audit data by scoring. Existing tests were not weakened.
