# Phase 24 Handoff — Approval Workflow

## Status

`READY FOR VALIDATION`

## Implemented

Phase 24 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/24-approval-workflow.md` and the Phase 24 plan:

- **Backend-enforced approval** — approve / reject / modify / cancel routes; frontend is projection-only
- **Final WARDEN recheck** — `PolicyEngine.evaluate` immediately before EXECUTE; stale revision and policy block fail closed
- **AuthorizedSimulationCommand** — allowlisted scenario templates map to `SimulationCommandType.EXECUTE` via `effect.set_asset_status` only
- **Idempotent execution** — `Idempotency-Key` + unique `(run_id, idempotency_key)` on `executed_actions`; duplicate approve returns prior result
- **Persistence** — `PostgresApprovalRepository`, `PostgresExecutedActionRepository`; `InvestigationDetailV1` **v4** with `approvals[]` / `executedActions[]`
- **Events** — `action.proposal.approved`, `action.proposal.rejected`, `action.proposal.modified`, `action.proposal.cancelled`, `action.executed`
- **Frontend** — `features/approval/` controls + extended `ProposalsPanel` inspection + realtime invalidation on approval/execution events
- **Actor identity** — synthetic operator (`asset:operator-console` + `synthetic-operator-token`) until Phase 30 OIDC
- **ADR** — `0025-approval-workflow.md`
- **Docs** — `docs/approval-workflow.md`; `docs/policy-and-proposals.md` lifecycle updated

**Explicitly not implemented:** Phase 25–26 replay, Phase 29 scoring/after-action UX, Phase 30 OIDC, Three.js.

## Files added / changed

| Area        | Key paths                                                                                                                                      |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Contracts   | `packages/contracts-python/src/aegis_contracts/approvals.py`, `packages/contracts-ts/src/approvals.ts`, InvestigationDetail v4, event registry |
| Mapping     | `apps/api/src/aegis_api/commands/mapping.py`                                                                                                   |
| Service     | `apps/api/src/aegis_api/approvals/service.py`                                                                                                  |
| API         | `apps/api/src/aegis_api/approvals/router.py`, `main.py` registration                                                                           |
| Persistence | `packages/persistence/.../repositories/approvals.py`, UoW + investigation aggregation                                                          |
| Frontend    | `apps/web/features/approval/**`, `proposals-panel.tsx`, `live-run-provider.tsx`                                                                |
| Tests       | `tests/approvals/**`, `tests/integration/approvals/**`, `tests/e2e/approval.spec.ts`                                                           |
| Docs        | `docs/approval-workflow.md`, ADR `0025-approval-workflow.md`, this handoff                                                                     |

## Contracts introduced or changed

| Contract                                             | Version         | Notes                                         |
| ---------------------------------------------------- | --------------- | --------------------------------------------- |
| `ApproveProposalRequestV1` / `ResponseV1`            | schema v1       | Approve + optional comment / expectedRevision |
| `RejectProposalRequestV1` / `ResponseV1`             | schema v1       | Reject + required reason                      |
| `ModifyProposalRequestV1` / `ResponseV1`             | schema v1       | Modification + re-WARDEN                      |
| `CancelProposalRequestV1` / `ResponseV1`             | schema v1       | Cancel without EXECUTE                        |
| `ProposalModificationV1`                             | schema v1       | Operator modification body                    |
| `FinalPolicyCheckV1`                                 | schema v1       | Pre-execute policy snapshot                   |
| `AuthorizedSimulationCommandV1`                      | schema v1       | Mapped EXECUTE payload                        |
| `ExecutionResultV1`                                  | schema v1       | Idempotent execution result                   |
| `StaleProposalErrorV1`                               | schema v1       | Stable `STALE_PROPOSAL` error                 |
| `InvestigationDetailV1`                              | schema **v4**   | Additive `approvals`, `executedActions`       |
| Events `action.proposal.rejected/modified/cancelled` | schema v1       | Approval lifecycle                            |
| `WORKSPACE_VERSION`                                  | `0.0.0-phase24` | Compatibility bump                            |

## Database migrations

- No new migration required — Phase 02 `approvals` / `executed_actions` tables suffice.
- Indexes/comments deferred; prefer no schema change when existing tables work.

## API routes

```text
POST /api/v1/action-proposals/{proposal_id}/approve
POST /api/v1/action-proposals/{proposal_id}/reject
POST /api/v1/action-proposals/{proposal_id}/modify
POST /api/v1/action-proposals/{proposal_id}/cancel
```

Headers: `X-Actor-Id` (default `asset:operator-console`), `Authorization: Bearer synthetic-operator-token`, optional `Idempotency-Key`.

## Commands executed and results

| Command                                                                                                                                                                                                                                                          | Result                                                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `pnpm check-contracts`                                                                                                                                                                                                                                           | **PASS**                                                                                                |
| `pnpm typecheck`                                                                                                                                                                                                                                                 | **PASS**                                                                                                |
| `pnpm lint`                                                                                                                                                                                                                                                      | **PASS** (Phase 24 files; workspace Prettier debt on regenerated schemas noted)                         |
| `pnpm test`                                                                                                                                                                                                                                                      | **PASS** (59 web/UI tests)                                                                              |
| `pnpm build`                                                                                                                                                                                                                                                     | **PASS**                                                                                                |
| `uv run ruff check apps/api/src/aegis_api/approvals apps/api/src/aegis_api/commands packages/persistence/src/aegis_persistence/repositories/approvals.py packages/contracts-python/src/aegis_contracts/approvals.py tests/approvals tests/integration/approvals` | **PASS**                                                                                                |
| `uv run pytest tests/approvals tests/integration/approvals -q`                                                                                                                                                                                                   | **PASS** (13 tests; Postgres via local install + `AEGIS_INTEGRATION_POSTGRES=1`)                        |
| `uv run pytest tests/contract tests/policy -q` (subset with approvals)                                                                                                                                                                                           | **PASS** (467 in focused run including contract/policy)                                                 |
| `uv run mypy apps services packages`                                                                                                                                                                                                                             | **KNOWN ISSUE** — duplicate module path (pre-existing)                                                  |
| `docker compose up -d postgres redis`                                                                                                                                                                                                                            | **ENV CAVEAT** — Docker unavailable; local Postgres 16 + Redis used                                     |
| `pnpm --filter @aegis/web test:e2e`                                                                                                                                                                                                                              | Spec added (`tests/e2e/approval.spec.ts`); browsers installed; fixture-mode screenshots captured        |
| Fixture-mode screenshot capture                                                                                                                                                                                                                                  | **PASS** — 12 screenshots under `/opt/cursor/artifacts/screenshots/`                                    |
| `pnpm exec playwright test approval` (from `apps/web`)                                                                                                                                                                                                           | **PASS** (3 e2e tests)                                                                                  |
| `pnpm format:check`                                                                                                                                                                                                                                              | **PARTIAL** — Phase 24 TS formatted; many pre-existing schema JSON files fail Prettier after full regen |

## Acceptance criteria evidence

| Criterion                                            | Evidence                                                                                                   |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Class 2/3 cannot execute without approval            | Integration + unit guards; unauthorized / missing token rejected; reject path writes no `ExecutedActionV1` |
| Double submission cannot duplicate effects           | Integration idempotency test: second approve returns same `executionId`, one executed_action row           |
| Modified proposals create revisions + renewed policy | Integration modify test: new revision + new `PolicyDecisionV1`; no EXECUTE until later approve             |
| Stale state fails closed                             | Integration + unit `StaleProposalError` / `STALE_PROPOSAL` on revision mismatch                            |

## Architecture decisions and ADRs

- **Created:** [0025-approval-workflow.md](../AEGIS-v1.0-Agent-Specs/adrs/0025-approval-workflow.md) (Status: **Proposed**)
- Cross-references ADR 0010 (command authority), ADR 0020 (agent runtime), ADR 0023 (BASTION/WARDEN), ADR 0024 (SCRIBE)

## Known limitations

- Docker Compose unavailable in this cloud environment; integration tests used local Postgres/Redis
- Actor identity remains synthetic until Phase 30 OIDC
- Full live Silent Relay → approve path depends on scenario package + agent chain; integration tests seed proposals directly for deterministic coverage
- `mypy` duplicate-module issue from earlier phases remains unresolved
- Regenerated JSON schemas may need a dedicated Prettier pass for `pnpm format:check` green on the full tree

## Deferred work

- Phase 25–26 replay / timeline reconstruction
- Phase 29 scoring and after-action UX
- Phase 30 OIDC actor replacement (swap point documented in ADR 0025 and `docs/approval-workflow.md`)
- Three.js / 3D visualization

## Risks preserved for Phases 25–29

- Approval/execution events remain append-only and sequence-monotonic for replay
- Actor hooks stay swappable without changing the approval state machine
- SCRIBE `human_decision` claims may optionally cite `ApprovalV1` but are not coupled beyond existing structure
