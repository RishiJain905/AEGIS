# Phase 21 Handoff — ORACLE

## Status

`READY FOR VALIDATION`

## Implemented

Phase 21 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/21-oracle.md`:

- **ORACLE** — competing evidence-grounded hypotheses, contradiction preservation, confidence assessments, append-only revisions, comparison matrix, bounded TRACE verification requests
- **Hypothesis tools** — read: `list_hypotheses`; analysis-write: `create_hypothesis_revision`, `request_trace_verification`, `retire_hypothesis`
- **Persistence** — migration `008_oracle_hypotheses`, `PostgresOracleHypothesisRepository`, extended `InvestigationDetailV1` v2 aggregation
- **API** — `POST /api/v1/runs/{run_id}/investigation/trigger-oracle`; existing `GET /incidents/{id}/investigation` returns hypothesis artifacts
- **Frontend** — ORACLE hypothesis cards, detail/provenance, comparison matrix, revision history, responsive layout
- **Tests** — `tests/agents/oracle/`, integration `test_oracle_flow.py`
- **Harness** — `scripts/run_oracle_harness.py`, `apps/web/scripts/capture-oracle-demo.mjs`
- **ADR** — `0022-oracle-hypothesis-generation.md`

**Explicitly not implemented:** BASTION, WARDEN, SCRIBE, approval workflows, containment execution, Three.js (Phases 22–23).

## Files added

| Area        | Key paths                                                                                                 |
| ----------- | --------------------------------------------------------------------------------------------------------- |
| Contracts   | `packages/contracts-python/src/aegis_contracts/hypothesis.py`, `packages/contracts-ts/src/hypothesis.ts`  |
| Migration   | `migrations/versions/008_oracle_hypotheses.py`                                                            |
| Persistence | `packages/persistence/src/aegis_persistence/repositories/hypothesis.py`                                   |
| ORACLE      | `services/agents/src/aegis_agents/roles/oracle/**`                                                        |
| Tools       | `services/agents/src/aegis_agents/tools/hypothesis/**`                                                    |
| API         | `apps/api/src/aegis_api/investigation/router.py` (trigger-oracle)                                         |
| Frontend    | `apps/web/features/investigation/investigation-panel.tsx`, `apps/web/fixtures/investigation-fixture.ts`   |
| Tests       | `tests/agents/oracle/**`, `tests/integration/agents/test_oracle_flow.py`                                  |
| Fixtures    | `fixtures/model-responses/oracle/**`, `fixtures/agent-workflows/oracle-hypothesis-generation.json`        |
| Scripts     | `scripts/run_oracle_harness.py`, `apps/web/scripts/capture-oracle-demo.mjs`                               |
| Docs        | `docs/agents/oracle.md`, `docs/handoffs/21-oracle-HANDOFF.md`, ADR `0022-oracle-hypothesis-generation.md` |

## Files modified

| File                                                               | Reason                                       |
| ------------------------------------------------------------------ | -------------------------------------------- |
| `packages/contracts-python/src/aegis_contracts/investigation.py`   | `InvestigationDetailV1` v2 hypothesis fields |
| `packages/contracts-python/src/aegis_contracts/entities.py`        | `HypothesisV1` v2 identity anchor            |
| `packages/contracts-python/src/aegis_contracts/events.py`          | Hypothesis domain events                     |
| `services/agents/src/aegis_agents/roles/registry.py`               | ORACLE handler registration                  |
| `services/agents/src/aegis_agents/runtime/registry.py`             | ORACLE tool map                              |
| `services/agents/src/aegis_agents/runtime/executor.py`             | ORACLE user prompt                           |
| `services/agents/src/aegis_agents/runtime/investigation_events.py` | Hypothesis event builders                    |
| `packages/model-provider/.../mock.py`                              | `phase21-oracle-v1` outputs                  |
| `apps/api/src/aegis_api/agents/observability.py`                   | ORACLE demo controls                         |
| `packages/contracts-*/versioning.*`                                | `WORKSPACE_VERSION=0.0.0-phase21`            |

## Contracts introduced or changed

| Contract                 | Version         | Notes                                    |
| ------------------------ | --------------- | ---------------------------------------- |
| `HypothesisRevisionV1`   | schema v1       | Append-only rich hypothesis content      |
| `HypothesisComparisonV1` | schema v1       | Support/contradiction matrix             |
| `VerificationRequestV1`  | schema v1       | Bounded TRACE follow-up                  |
| `ConfidenceAssessmentV1` | schema v1       | Point + range + coverage + penalty       |
| `HypothesisClaimV1`      | schema v1       | Grounded claim with `ClaimKindV1`        |
| `HypothesisV1`           | schema v2       | Identity anchor with `currentRevisionId` |
| `InvestigationDetailV1`  | schema v2       | Hypothesis artifact aggregation          |
| `TriggerOracleRequestV1` | schema v1       | Trigger API                              |
| `WORKSPACE_VERSION`      | `0.0.0-phase21` | Compatibility bump                       |

## Database migrations

- `008_oracle_hypotheses.py` — `hypothesis_revisions`, `hypothesis_comparisons`, `verification_requests`

## Commands executed and results

| Command                                                         | Result                                                                                |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `uv run ruff check .`                                           | **PASS**                                                                              |
| `uv run mypy apps services packages`                            | **KNOWN ISSUE** — duplicate module path `aegis_agents.runtime.factory` (pre-existing) |
| `uv run pytest -q`                                              | **PASS**                                                                              |
| `uv run pytest tests/agents/oracle -q`                          | **PASS**                                                                              |
| `uv run pytest tests/integration/agents/test_oracle_flow.py -q` | **PASS** (with PostgreSQL)                                                            |
| `uv run lint-imports`                                           | **PASS**                                                                              |
| `pnpm check-contracts`                                          | **PASS**                                                                              |
| `pnpm typecheck`                                                | **PASS**                                                                              |
| `pnpm lint`                                                     | **PASS**                                                                              |
| `pnpm test`                                                     | **PASS**                                                                              |
| `uv run python scripts/run_oracle_harness.py`                   | Requires PostgreSQL                                                                   |
| `node apps/web/scripts/capture-oracle-demo.mjs`                 | Fixture-mode UI screenshots                                                           |

## Architecture decisions and ADRs

- **Created:** [0022-oracle-hypothesis-generation.md](../AEGIS-v1.0-Agent-Specs/adrs/0022-oracle-hypothesis-generation.md) (Status: **Proposed**)
- Cross-references ADR 0021 (WATCHTOWER/TRACE), ADR 0020 (agent runtime), ADR 0019 (model provider)

## Known limitations

- Full-stack ORACLE harness requires PostgreSQL (`docker compose up -d postgres redis`)
- ORACLE coordinator requires prior WATCHTOWER triage on the investigation
- Recorded provider fixtures for ORACLE use mock adapter JSON; additional variant fixtures are optional for rejection tests
- `mypy` duplicate-module issue from Phase 19/20 remains unresolved

## Deferred work

- Phase 22 BASTION/WARDEN response planning and execution
- Phase 23 SCRIBE reporting
- Approval workflows and containment execution
- Automatic post-TRACE ORACLE worker hook (manual/API trigger implemented)

## Risks for dependent phases

- BASTION must consume current hypothesis revisions via `InvestigationDetailV1`, not overwrite ORACLE history
- WARDEN policy must evaluate proposals against visible hypothesis confidence and contradictions
- Phases 22–23 must preserve Phase 19 runtime semantics and tool authorization boundaries

## Acceptance criteria evidence

| Criterion                                             | Evidence                                                               |
| ----------------------------------------------------- | ---------------------------------------------------------------------- |
| Multiple competing hypotheses generated               | `test_oracle_acceptance_criteria.py`, integration flow, fixture UI     |
| Claims grounded to visible evidence                   | `test_oracle_grounding.py`                                             |
| Contradictions preserved and visible                  | `test_oracle_grounding.py`, investigation panel contradictions section |
| Confidence range/coverage/penalty validated           | `test_oracle_confidence.py`                                            |
| Append-only revisions (supersede/retire)              | `test_oracle_acceptance_criteria.py`, revision history UI              |
| ORACLE tool authorization boundaries                  | `test_oracle_tool_permissions.py`, harness unauthorized tool check     |
| No simulation mutation                                | ORACLE handler persists analysis artifacts only                        |
| Investigation detail API returns hypothesis artifacts | `InvestigationDetailV1` v2, integration test                           |
| Realtime invalidation on hypothesis events            | `investigation.*` prefix in live-run provider                          |
| Command centre hypothesis UI                          | `investigation-panel.tsx`, capture script screenshots                  |
