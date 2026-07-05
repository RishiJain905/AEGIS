# Phase 20 Handoff — WATCHTOWER and TRACE

## Status

`READY FOR VALIDATION`

## Implemented

Phase 20 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/20-watchtower-and-trace.md`:

- **WATCHTOWER** — deterministic alert correlation, structured triage (`WatchtowerTriageResultV1`), incident create/update, idempotent triggers, TRACE task coordination via Phase 19 runtime
- **TRACE** — bounded investigation plans, evidence collection with provenance, contradiction preservation, graph expansion overlays (`AgentGraphOverlayV1`), candidate affected assets
- **Investigation tools** — read: `search_events`, `get_asset`, `get_relationships`, `get_paths`, `get_risk_scores`, `list_alerts`, `get_alert`, `list_existing_evidence`; analysis-write: `attach_evidence`, `create_investigation_note`
- **Persistence** — migration `007_investigation_agents`, `PostgresInvestigationRepository`, investigation domain events
- **API** — `GET /api/v1/incidents/{id}`, `GET /api/v1/incidents/{id}/investigation`, `POST /api/v1/runs/{run_id}/investigation/trigger-watchtower`
- **Frontend** — `apps/web/features/investigation/`, inspector integration, graph overlay highlights, realtime invalidation
- **Tests** — `tests/agents/watchtower/`, `tests/agents/trace/`, integration flow test (PostgreSQL)
- **Harness** — `scripts/run_watchtower_trace_harness.py`, `apps/web/scripts/capture-watchtower-trace-demo.mjs`
- **ADR** — `0021-watchtower-trace-investigation-agents.md`

**Explicitly not implemented:** ORACLE, BASTION, WARDEN, SCRIBE, approval workflows, containment execution, Three.js (Phases 21–23).

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/investigation.py`, `packages/contracts-ts/src/investigation.ts` |
| Migration | `migrations/versions/007_investigation_agents.py` |
| Persistence | `packages/persistence/src/aegis_persistence/repositories/investigation.py`, ORM rows in `orm/tables.py` |
| WATCHTOWER | `services/agents/src/aegis_agents/roles/watchtower/**` |
| TRACE | `services/agents/src/aegis_agents/roles/trace/**` |
| Tools | `services/agents/src/aegis_agents/tools/investigation/**` |
| Runtime | `services/agents/src/aegis_agents/runtime/investigation_events.py`, role dispatch in `executor.py` |
| API | `apps/api/src/aegis_api/investigation/router.py` |
| Frontend | `apps/web/features/investigation/**`, `apps/web/fixtures/investigation-fixture.ts` |
| Tests | `tests/agents/watchtower/**`, `tests/agents/trace/**`, `tests/integration/agents/test_watchtower_trace_flow.py` |
| Fixtures | `fixtures/model-responses/watchtower-trace/**`, `fixtures/agent-workflows/watchtower-triage.json`, etc. |
| Scripts | `scripts/run_watchtower_trace_harness.py`, `apps/web/scripts/capture-watchtower-trace-demo.mjs` |
| Docs | `docs/handoffs/20-watchtower-and-trace-HANDOFF.md`, ADR `0021-watchtower-trace-investigation-agents.md` |

## Files modified

| File | Reason |
|------|--------|
| `services/agents/src/aegis_agents/runtime/registry.py` | Phase 20 tool maps and prompt versions |
| `services/agents/src/aegis_agents/runtime/executor.py` | Role handler dispatch |
| `services/agents/src/aegis_agents/tools/definitions.py`, `handlers.py` | Investigation tool merge |
| `packages/model-provider/.../mock.py` | Role-aware Phase 20 outputs |
| `apps/api/src/aegis_api/main.py` | Investigation router |
| `apps/api/src/aegis_api/agents/observability.py` | Phase 20 demo controls |
| `apps/web/features/shell/components/inspector-panel.tsx` | Investigation panel |
| `apps/web/features/live-run/live-run-provider.tsx` | Realtime invalidation |
| `apps/web/features/operational-graph/components/operational-graph-view.tsx` | Graph overlays |
| `packages/contracts-*/versioning.*` | `WORKSPACE_VERSION=0.0.0-phase20` |
| `tests/contract/fixtures/compatibility-manifest.json` | Phase 20 schema parity |

## Contracts introduced or changed

| Contract | Version | Notes |
|----------|---------|-------|
| `WatchtowerTriageResultV1` | schema v1 | Triage/correlation artifact |
| `TraceInvestigationPlanV1` | schema v1 | Bounded search plan |
| `EvidenceAttachmentV1` | schema v1 | Grounded facts + contradictions |
| `CandidateAffectedAssetV1` | schema v1 | Affected asset ranking |
| `InvestigationNoteV1` | schema v1 | Analysis notes (not hypotheses) |
| `AgentGraphOverlayV1` | schema v1 | Graph layer 4 highlights |
| `InvestigationDetailV1` | schema v1 | API aggregate |
| `TriggerWatchtowerRequestV1` | schema v1 | Trigger API |
| `WORKSPACE_VERSION` | `0.0.0-phase20` | Compatibility bump |

## Database migrations

- `007_investigation_agents.py` — investigation artifact tables

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run mypy apps services packages` | **KNOWN ISSUE** — duplicate module path `aegis_agents.runtime.factory` (same class as Phase 19) |
| `uv run pytest -q` | **PASS** — 574 passed, 42 skipped |
| `uv run pytest tests/agents/watchtower tests/agents/trace -q` | **PASS** — 26 passed |
| `uv run lint-imports` | **PASS** — 4 kept, 0 broken |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm lint` | **PASS** |
| `pnpm test` | **PASS** |
| `uv run python scripts/run_watchtower_trace_harness.py` | **BLOCKED** — requires PostgreSQL (unavailable in cloud agent VM) |
| `node apps/web/scripts/capture-watchtower-trace-demo.mjs` | **PARTIAL** — fixture-mode UI screenshots captured; harness PG steps failed |

## Architecture decisions and ADRs

- **Created:** [0021-watchtower-trace-investigation-agents.md](../AEGIS-v1.0-Agent-Specs/adrs/0021-watchtower-trace-investigation-agents.md) (Status: **Proposed**)
- Cross-references ADR 0020 (agent runtime), ADR 0019 (model provider)

## Known limitations

- Full-stack Silent Relay + WATCHTOWER/TRACE harness requires PostgreSQL (docker compose)
- `GET /incidents/{id}` on runs router deprecated stub remains for backward compatibility; canonical route is investigation router
- WATCHTOWER coordinator creates incidents when none exist; does not run detection/risk pipelines automatically
- Graph overlay application in UI requires Investigation layer toggle enabled

## Deferred work

- Phase 21 ORACLE hypothesis generation
- Phase 22 BASTION/WARDEN response planning and execution
- Phase 23 SCRIBE reporting
- Approval workflows and containment execution
- Automatic post-detection WATCHTOWER worker hook (manual/API trigger implemented)

## Risks for dependent phases

- ORACLE must consume `EvidenceAttachmentV1` including `isContradiction=true` records without deletion
- BASTION/WARDEN must not bypass investigation artifact contracts when proposing actions
- Phases 21–23 must preserve Phase 19 runtime semantics and tool authorization boundaries

## Acceptance criteria evidence

| Criterion | Evidence |
|-----------|----------|
| Silent Relay signals → grounded investigation | `WatchtowerCoordinator`, `TraceRoleHandler`, integration test `test_watchtower_trace_flow.py`, fixture UI at `/incidents/incident:inc_synthetic_001` |
| Every collected fact resolves to authoritative data | `handle_attach_evidence` validates source refs; `test_evidence_grounding.py` |
| Search and graph expansion are bounded | `InvestigationBudgetTracker`, `test_bounded_search.py`, plan `maxHops`/`maxToolCalls` |
| Contradictory evidence preserved for ORACLE | `isContradiction` on attachments, no delete path, `test_evidence_grounding.py` |

## Prohibited-shortcut confirmation

- No parallel agent runtime or direct model SDK calls from roles/tools
- No `create_action_proposal` on WATCHTOWER/TRACE tool maps
- No ORACLE/BASTION/WARDEN/SCRIBE implementation
- Tests map to acceptance criteria; validation commands executed honestly
