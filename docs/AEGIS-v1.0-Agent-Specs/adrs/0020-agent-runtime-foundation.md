# ADR 0020: Agent Runtime Foundation (Phase 19)

## Status

Proposed — awaiting project-owner approval.

## Context

Phases 20–23 require a shared incident-scoped agent runtime with audited tool calls, grounding validation, budgets, deterministic CI fixtures, and failure isolation from simulation state. Phase 19 must not implement role-specific defensive agents or simulator mutation.

## Decision

1. **Contracts:** Agent runtime contracts live in `aegis_contracts.agent_runtime` (not a separate `agent-contracts` package). TypeScript mirror in `@aegis/contracts-ts`.

2. **Session vs task:** `AgentSessionV1` is the incident-scoped state machine. `AgentTaskV1` is the idempotent execution unit with bounded retry semantics.

3. **Tool authorization:** Server-side only. `ToolRegistry` + `permissions.py` enforce role allowlists and tool class rules. `execution`-class tools are never model-visible.

4. **Model calls:** All LLM access via Phase 18 `AgentGenerationFacade` → `GenerationService`. No direct vendor SDK imports in `services/agents`.

5. **Persistence:** PostgreSQL is authoritative for sessions, tasks, transitions, tool invocations, and artifacts. Agent-domain events use the outbox pattern.

6. **Failure isolation:** Executor catches failures, persists terminal task/session state, and never propagates to simulation `Run` lifecycle.

7. **Recovery:** On startup, `running` tasks are marked failed per recovery policy (documented in handoff).

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Separate `packages/agent-contracts` | Violates `docs/contracts/versioning.md`; duplicates canonical packages |
| Model-visible execution tools | Violates architecture §14 tool-class isolation |
| Direct OpenAI in executor | Violates Phase 18 adapter boundary |
| In-memory-only agent state | Violates PostgreSQL authority requirement |

## Consequences

- Phases 20–23 extend `AgentDefinitionRegistry` with role-specific prompts/logic without changing core executor contracts
- Recorded fixtures under `fixtures/model-responses/` enable deterministic agent-step replay
- Worker `agent-runtime` mode provides async task polling; API harness supports synchronous CI runs

## Cross-references

- ADR 0019 — Model Provider Abstraction (Phase 18)
- `docs/agents/runtime.md` — operational documentation
- `docs/AEGIS-v1.0-Agent-Specs/agent-system/19-agent-runtime.md` — acceptance spec

## Approval

- [ ] Project owner
