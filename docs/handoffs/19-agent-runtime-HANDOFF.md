# Phase 19 Handoff — Agent Runtime

## Status

`READY FOR VALIDATION`

## Implemented

Phase 19 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/19-agent-runtime.md`:

- Canonical agent runtime contracts (`AgentDefinitionV1`, `AgentTaskV1`, `ToolDefinitionV1`, `ToolInvocationV1`, `AgentArtifactV1`, API DTOs) in `aegis_contracts.agent_runtime` / `@aegis/contracts-ts`
- Migration `006_agent_runtime` — `agent_tasks`, `agent_state_transitions`, `tool_invocations`, `agent_artifacts`; `agent_sessions.budget`
- Runtime: registry, state machine, session/task services, executor, grounding, budget, errors, recovery, harness seed
- Tools: registry, permissions, validator, executor, read/analysis/proposal handlers; execution class hidden
- API routes `/api/v1/incidents/.../agent-sessions`, task/cancel/retry, registry; observability `/agents/observability`
- Worker mode `--mode agent-runtime`
- Recorded agent-step fixture `fixtures/model-responses/recorded/agent-step-v1.json`
- Tests: `tests/agents/runtime/`, `tests/integration/agents/`
- ADR 0020, `docs/agents/runtime.md`
- Harness `scripts/run_agent_runtime_harness.py`, screenshot script `apps/web/scripts/capture-agent-runtime-demo.mjs`

**Explicitly not implemented:** WATCHTOWER/TRACE/ORACLE/BASTION/WARDEN/SCRIBE role-specific reasoning, approval workflows, simulator execution, shell/network tools (Phases 20–23).

## Files added

| Area      | Key paths                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------------------------- |
| Contracts | `packages/contracts-python/src/aegis_contracts/agent_runtime.py`, `packages/contracts-ts/src/agent-runtime.ts` |
| Migration | `migrations/versions/006_agent_runtime.py`                                                                     |
| Runtime   | `services/agents/src/aegis_agents/runtime/**`                                                                  |
| Tools     | `services/agents/src/aegis_agents/tools/**`                                                                    |
| API       | `apps/api/src/aegis_api/agents/**`                                                                             |
| Worker    | `services/workers/src/aegis_workers/agent_runtime_runner.py`                                                   |
| Fixtures  | `fixtures/agent-workflows/**`, `fixtures/model-responses/recorded/agent-step-v1.json`                          |
| Tests     | `tests/agents/runtime/**`, `tests/integration/agents/**`                                                       |
| Docs      | `docs/agents/runtime.md`, ADR `0020-agent-runtime-foundation.md`                                               |
| Scripts   | `scripts/run_agent_runtime_harness.py`, `apps/web/scripts/capture-agent-runtime-demo.mjs`                      |

## Contracts introduced or changed

| Contract                                                 | Version         | Notes                     |
| -------------------------------------------------------- | --------------- | ------------------------- |
| `AgentDefinitionV1` / `AgentTaskV1` / `ToolDefinitionV1` | schema v1       | Core runtime entities     |
| `ToolInvocationV1` / `AgentArtifactV1`                   | schema v1       | Audited execution records |
| `AgentSessionDetailV1`                                   | schema v1       | API aggregate DTO         |
| Runtime ID prefixes                                      | —               | `atk_`, `tiv_`, `aaf_`    |
| `WORKSPACE_VERSION`                                      | `0.0.0-phase19` | Compatibility bump        |

## Database migrations

- `006_agent_runtime.py` — agent runtime tables + tool seeds

## Commands executed and results

| Command                                                | Result                                                                                                                                                |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run ruff check .`                                  | **PASS**                                                                                                                                              |
| `uv run mypy apps services packages`                   | **KNOWN ISSUE** — duplicate module path for `aegis_agents.runtime.factory` (services package layout; same class of issue as Phase 18 `db/session.py`) |
| `uv run pytest -q`                                     | **PASS** — 526 passed, 41 skipped                                                                                                                     |
| `uv run pytest tests/agents/runtime -q`                | **PASS** — 18 passed                                                                                                                                  |
| `uv run pytest tests/integration/agents -q`            | **SKIPPED** — requires PostgreSQL (unavailable in cloud agent VM)                                                                                     |
| `uv run lint-imports`                                  | **PASS** — 4 kept, 0 broken                                                                                                                           |
| `pnpm check-contracts`                                 | **PASS**                                                                                                                                              |
| `pnpm typecheck`                                       | **PASS**                                                                                                                                              |
| `pnpm lint`                                            | **PASS**                                                                                                                                              |
| `pnpm test`                                            | **PASS**                                                                                                                                              |
| `uv run python scripts/run_agent_runtime_harness.py`   | **BLOCKED** — requires PostgreSQL                                                                                                                     |
| `node apps/web/scripts/capture-agent-runtime-demo.mjs` | **PARTIAL** — command centre captured; agent harness panels require PostgreSQL-backed API                                                             |

## Architecture decisions and ADRs

- **Created:** [0020-agent-runtime-foundation.md](../AEGIS-v1.0-Agent-Specs/adrs/0020-agent-runtime-foundation.md) (Status: **Proposed**)
- Cross-references ADR 0019 (model provider)

## Known limitations

- Recovery policy marks orphaned `running` tasks as `failed` on startup (no automatic resume)
- Observability harness seeds incident via `POST /api/v1/agents/harness/seed`
- Recorded provider replay requires exact request fingerprint match (`phase19-v1` prompt)
- Integration tests and harness require PostgreSQL

## Deferred work

- Phase 20+ role-specific agent implementations
- Approval workflow integration
- Simulator execution tools (server-only stub exists for negative tests)
- Streaming model responses

## Validation evidence for reviewers

1. Unit tests in `tests/agents/runtime/` cover state machine, tool permissions, grounding, budget, failure isolation, acceptance criteria
2. Integration tests in `tests/integration/agents/` cover persistence, idempotency, recovery, auditability, recorded replay (run with PostgreSQL)
3. Observability harness at `/agents/observability` demonstrates registry, mock/recorded tasks, tool auth, lifecycle audit
4. Generic Phase 19 runtime only — defensive agent roles are registry placeholders
