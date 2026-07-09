# ADR 0027 — Replay Frontend

## Status

Proposed

## Context

Phase 25 delivered the authoritative snapshot/replay engine and read-only `/api/v1/replay` APIs. Phase 26 must provide interactive historical scrubbing without:

- duplicating reconstruction in the browser
- mutating live simulation, approvals, events, evidence, reports, or audit
- implying that replay transport controls the live run
- absorbing Phase 27–29 Three.js / cinematic / scoring scope

The application shell already mounts `LiveRunProvider` for `/runs/[runId]`. A distinct historical path is required.

## Decision

1. **Phase 25 remains the reconstruction authority.** The frontend only requests `ReplayStateV1` / `StateDiffV1` / snapshot manifests from `/api/v1/replay/...` and renders projections.

2. **Distinct historical UI store.** `apps/web/stores/replay-store.ts` holds cursor, playback, bookmarks, comparison, and reconstructed state. It never writes into the live WebSocket reducer.

3. **Route isolation.** `/replay/[runId]` mounts `ReplayCommandCentreShell` + `ReplayProvider` and does **not** mount `LiveRunProvider`.

4. **Sequence-primary shared cursor.** Graph, timeline, and inspector share one `ReplayCursorV1.sequence`. Rapid scrubbing cancels in-flight reconstruct requests via `AbortController` + generation counters.

5. **Return-to-live requires authoritative resync.** Exit navigates to `/runs/[runId]` with `ReturnToLiveResultV1.authoritativeResyncRequired = true` and clears the replay store. No merge of historical state into live state.

6. **Canonical frontend contracts** live in shared packages (`ReplayViewStateV1`, `ReplayBookmarkV1`, `ReplayComparisonV1`, `TimelineFilterV1`, `HistoricalGraphAdapterV1`, `ReturnToLiveResultV1`), not a second package.

7. **No cinematic / Three.js / scoring** in this phase. Sigma.js remains the analysis graph.

## Consequences

- Phases 27–29 must consume the same historical store/cursor semantics and must not invent a second reconstruction path.
- Fixture-mode replay projections exist for local UI/e2e; production path always uses Phase 25 APIs.
- Visual historical-mode labeling is mandatory whenever replay controls are shown.

## References

- `docs/AEGIS-v1.0-Agent-Specs/human-control-and-replay/26-replay-frontend.md`
- ADR 0026 — Snapshot and Replay Engine
- ADR 0014 — Live Command-Centre Integration
- `docs/architecture.md` §11
