# ADR 0014: Live Command-Centre Integration

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 12 delivered the WebSocket gateway and `@aegis/realtime-client`, but the command centre remained fixture-backed. Phase 13 must connect PostgreSQL-authoritative runs, graph snapshots, Redis/WebSocket delivery, and the Sigma.js operational graph through one sequence-aware frontend reducer without creating competing client state stores.

Requirements:

- Shared `lastAppliedSequence` across graph, timeline, and run status
- Bootstrap from authoritative snapshots; apply incremental graph deltas thereafter
- Distinct connection-health states with stale-state protection
- Thin run command HTTP APIs with idempotency
- Preserve Graphology as semantic source of truth; Sigma.js as renderer only

## Decision

1. **Phase 13 contracts** (`RunReplicatedState`, `RealtimeReducerAction`, `ConnectionHealthState`, `SnapshotBootstrapPayloadV1`) live in `@aegis/contracts-ts` / `aegis_contracts.live_run` with schema version 1.

2. **Backend run APIs** at `apps/api/src/aegis_api/runs/` delegate to `RunCommandService` and `GraphProjectionService`. PostgreSQL `graph_snapshots` stores authoritative bootstrap/resync snapshots; domain events remain authoritative for history.

3. **Frontend reducer** in `apps/web/lib/realtime/` applies a pure sequence-aware reducer. `@aegis/realtime-client` handles transport only; TanStack Query owns HTTP bootstrap and run commands; Zustand remains limited to ephemeral UI selection/panel prefs.

4. **Event projection rules:** `sim.asset.status_changed` → `GraphDeltaV1` upsert_node; lifecycle events → run status; telemetry/alert/incident → timeline entries; duplicates suppressed by `eventId`/sequence; gaps halt application until PostgreSQL catch-up or snapshot resync.

5. **Cursor persistence** in `sessionStorage` keyed by run ID for reload/reconnect. Resync handles both `snapshot_required` and `WS_SEQUENCE_GAP`.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| TanStack Query cache as live event store | Violates architecture; competes with reducer semantics |
| Direct Sigma mutation from WebSocket handlers | Breaks Graphology source-of-truth rule |
| Full event-sourced client rebuild only | Too slow for large Silent Relay graphs; snapshots required |
| Auto-advance background worker | Deferred; minimal step API sufficient for Phase 13 demo |

## Consequences

- Phase 14+ feature engineering must consume `RunReplicatedState` reducer outputs, not raw WebSocket frames.
- API restart requires deterministic runtime restore from persisted events (bounded step replay).
- Changing projection rules or connection-health semantics requires contract version bump and ADR update.

## Approval

- [ ] Project owner
