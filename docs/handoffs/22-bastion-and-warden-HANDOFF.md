# Phase 22 Handoff — BASTION and WARDEN

## Status

`READY FOR VALIDATION`

## Implemented

Phase 22 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/22-bastion-and-warden.md`:

- **BASTION** — evidence-grounded response proposals with 1–3 options, append-only revisions, `create_response_proposal` tool
- **WARDEN** — deterministic `PolicyEngine` evaluation; model prose is non-authoritative
- **Policy package** — `packages/policy` with allowlist, class mapping, stale revision block, scenario restrictions
- **Persistence** — migration `009_bastion_warden_proposals`, `PostgresProposalRepository`, `InvestigationDetailV1` v3 aggregation
- **API** — `POST /api/v1/runs/{run_id}/investigation/trigger-bastion`, `trigger-warden`
- **Frontend** — `ProposalsPanel` in inspector, policy outcome badges, lifecycle audit, Phase 24 read-only approval state
- **Tests** — `tests/policy/`, `tests/agents/bastion/`, `tests/agents/warden/`, integration `test_bastion_warden_flow.py`
- **Harness** — `scripts/run_bastion_warden_harness.py`, `apps/web/scripts/capture-bastion-warden-demo.mjs`
- **ADR** — `0023-bastion-warden-policy-proposals.md`

**Explicitly not implemented:** SCRIBE (Phase 23), approval UI/execution (Phase 24), simulator command execution, Three.js.

## Files added

| Area        | Key paths                                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Contracts   | `packages/contracts-python/src/aegis_contracts/proposals.py`, `packages/contracts-ts/src/proposals.ts`                         |
| Policy      | `packages/policy/src/aegis_policy/commands.py`, `engine.py`                                                                    |
| Migration   | `migrations/versions/009_bastion_warden_proposals.py`                                                                          |
| Persistence | `packages/persistence/src/aegis_persistence/repositories/proposals.py`                                                         |
| BASTION     | `services/agents/src/aegis_agents/roles/bastion/**`                                                                            |
| WARDEN      | `services/agents/src/aegis_agents/roles/warden/**`                                                                             |
| Tools       | `services/agents/src/aegis_agents/tools/proposal/**`                                                                           |
| Events      | `services/agents/src/aegis_agents/runtime/proposal_events.py`                                                                  |
| Frontend    | `apps/web/features/proposals/proposals-panel.tsx`                                                                              |
| Tests       | `tests/policy/**`, `tests/agents/bastion/**`, `tests/agents/warden/**`, `tests/integration/agents/test_bastion_warden_flow.py` |
| Fixtures    | `fixtures/model-responses/bastion/**`, `fixtures/model-responses/warden/**`                                                    |
| Scripts     | `scripts/run_bastion_warden_harness.py`, `apps/web/scripts/capture-bastion-warden-demo.mjs`                                    |
| Docs        | `docs/policy-and-proposals.md`, ADR `0023-bastion-warden-policy-proposals.md`                                                  |

## Contracts introduced or changed

| Contract                                             | Version         | Notes                                  |
| ---------------------------------------------------- | --------------- | -------------------------------------- |
| `ResponseOptionV1`                                   | schema v1       | Evidence-grounded response option      |
| `ProposalRevisionV1`                                 | schema v1       | Append-only proposal body              |
| `PolicyInputV1` / `PolicyDecisionV1`                 | schema v1       | Deterministic evaluation               |
| `ApprovalRequirementV1`                              | schema v1       | Phase 24 gate metadata                 |
| `ActionProposalV1`                                   | schema v2       | `currentRevisionId`, `scenarioCommand` |
| `InvestigationDetailV1`                              | schema v3       | Proposal/policy aggregation            |
| `TriggerBastionRequestV1` / `TriggerWardenRequestV1` | schema v1       | Trigger APIs                           |
| Event `action.proposal.policy_evaluated`             | schema v1       | WARDEN outcome                         |
| `WORKSPACE_VERSION`                                  | `0.0.0-phase22` | Compatibility bump                     |

## Database migrations

- `009_bastion_warden_proposals.py` — `proposal_revisions`, `policy_decisions`

## Commands executed and results

| Command                                                                  | Result                                                                 |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `uv run ruff check .`                                                    | **PASS**                                                               |
| `uv run pytest tests/policy tests/agents/bastion tests/agents/warden -q` | **PASS** (14 tests)                                                    |
| `uv run pytest tests/policy tests/agents tests/contract -q`              | **PASS** (410 tests; boundary test env caveat below)                   |
| `uv run mypy apps services packages`                                     | **KNOWN ISSUE** — duplicate module path + fastapi stubs (pre-existing) |
| `uv run lint-imports`                                                    | **ENV CAVEAT** — requires full workspace packages on PYTHONPATH        |
| `pnpm check-contracts`                                                   | **PASS**                                                               |
| `pnpm typecheck`                                                         | **PASS**                                                               |
| `pnpm lint`                                                              | **PASS**                                                               |
| `pnpm test`                                                              | **PASS** (59 web tests)                                                |
| `node apps/web/scripts/capture-bastion-warden-demo.mjs`                  | **PASS** (fixture-mode screenshots)                                    |
| `uv run python scripts/run_bastion_warden_harness.py`                    | Requires PostgreSQL                                                    |
| `uv run pytest tests/integration/agents/test_bastion_warden_flow.py`     | Requires `AEGIS_INTEGRATION_POSTGRES=1` + PostgreSQL                   |

## Visual evidence

Fixture-mode screenshots captured to `/opt/cursor/artifacts/screenshots/`:

1. `01-silent-relay-running.png` — Operation Silent Relay command centre
2. `02-oracle-hypotheses-evidence.png` — ORACLE hypotheses + investigation evidence
3. `03-bastion-proposals-panel.png` — BASTION proposals panel
4. `04-proposal-detail-evidence-rationale.png` — Selected proposal with evidence, rationale, assets
5. `05-warden-policy-approval-required.png` — WARDEN approval-required outcome
6. `06-approval-required-pending.png` — Pending proposal awaiting Phase 24 approval
7. `07-policy-allow-and-block.png` — Allow + block policy outcomes
8. `08-blocked-malformed-proposal.png` — Observability blocked proposal demo
9. `09-proposal-lifecycle-audit.png` — Lifecycle and audit records
10. `10-mock-deterministic-bastion.png` — Observability BASTION trigger
11. `11-realtime-proposal-update.png` — Realtime UI with policy results
12. `12-responsive-proposals.png` — Narrow viewport layout
13. `22-bastion-warden-ci-evidence.png` — CI test output panel

## Architecture decisions and ADRs

- **Created:** [0023-bastion-warden-policy-proposals.md](../AEGIS-v1.0-Agent-Specs/adrs/0023-bastion-warden-policy-proposals.md) (Status: **Proposed**)
- Cross-references ADR 0022 (ORACLE), ADR 0020 (agent runtime)

## Known limitations

- Full-stack BASTION/WARDEN harness requires PostgreSQL (`docker compose up -d postgres redis`)
- BASTION coordinator requires prior ORACLE hypotheses on the investigation
- Class 2/3 proposals stay `pending` with `approval_required`; no execution in Phase 22
- `mypy` duplicate-module issue from Phase 19/20 remains unresolved
- `lint-imports` in minimal dev env may require additional workspace packages on PYTHONPATH

## Deferred work

- Phase 23 SCRIBE reporting
- Phase 24 approval UI, approve/reject routes, simulator command execution
- Pre-execution policy revalidation wiring at approval time (stale revision block is implemented)
