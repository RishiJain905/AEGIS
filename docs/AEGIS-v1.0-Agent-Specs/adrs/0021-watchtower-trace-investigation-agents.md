# ADR 0021 — WATCHTOWER and TRACE Investigation Agents

## Status

Proposed

## Context

Phase 20 introduces WATCHTOWER (alert triage/correlation) and TRACE (bounded evidence gathering and graph expansion) as the first role-specific agents on the Phase 19 generic agent runtime. Investigation artifacts must be persisted, auditable, and delivered to the command centre without creating a parallel orchestration system or allowing direct simulation mutation.

## Decision

1. **Role plugin pattern on Phase 19 runtime** — WATCHTOWER and TRACE extend `TaskExecutor` via `RoleHandler` implementations (`output_schema`, `system_prompt`, `post_process`). All model calls use the Phase 18 `ModelProvider` abstraction.

2. **Investigation artifact tables** — Durable triage results, trace plans, evidence attachments, investigation notes, candidate affected assets, and graph overlays are stored in PostgreSQL tables (`007_investigation_agents` migration) with schema-versioned JSON payloads.

3. **Investigation domain events** — `investigation.triage.completed`, `investigation.plan.created`, `investigation.evidence.attached`, and `investigation.graph.overlay` are emitted append-only with monotonic run sequence numbers for realtime projection.

4. **Tool boundaries** — WATCHTOWER and TRACE use read and analysis-write investigation tools only. `create_hypothesis`, `create_action_proposal`, and execution-class tools are excluded from their allowlists. Tool authorization remains server-side.

5. **Explicit deferral of later phases** — ORACLE hypothesis generation, BASTION/WARDEN response planning, SCRIBE reporting, approval workflows, and containment execution remain out of scope.

## Consequences

- Phases 21–23 must consume investigation artifacts via `InvestigationDetailV1` and existing agent session audit records.
- Contradictory evidence is preserved via `isContradiction` on `EvidenceAttachmentV1` for ORACLE.
- Graph overlays are semantic projections (layer 4), not authoritative graph state.

## References

- `docs/AEGIS-v1.0-Agent-Specs/agent-system/20-watchtower-and-trace.md`
- ADR 0020 — Agent Runtime Foundation
- ADR 0019 — Model Provider Abstraction
