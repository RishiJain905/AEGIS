# AEGIS Cinematic Incident Replay

> Phase 28 — directed camera chapters and presentation effects over authoritative historical replay.

## Purpose

Provide a cinematic presentation mode for completed or partially completed runs (especially Operation Silent Relay). Camera scenes, captions, and chapter navigation are derived from Phase 25 reconstructed `ReplayStateV1` and driven through the Phase 26 replay cursor and Phase 27 Three.js semantic renderer.

**Not in this phase:** scoring, final after-action UX, prerendered video export, or production auth (Phase 29+).

## Architecture boundary

```text
Phase 25 GET /api/v1/replay/.../state  →  ReplayStateV1
        ↓
useReplayStore (ReplayCursorV1)  →  GraphStore
        ↓
CinematicBeatPlanner → CinematicPlanV1 (beats/chapters/directives)
        ↓
CameraDirector (presentation only)
        ↓
┌──────────────────────┬────────────────────────────┐
│ Sigma 2D analysis    │ SemanticSceneAdapter + R3F │
│ (Open in 2D jump)    │ CameraBookmark3D apply     │
└──────────────────────┴────────────────────────────┘
```

Rules:

- Do not invent nodes, edges, risk, incidents, evidence, agents, proposals, approvals, or reports.
- Camera position/transitions never mutate PostgreSQL, domain events, or live run state.
- Presentation hints must not reveal hidden causes before evidence (`revealsHiddenCause: false`).
- Chronology follows sequence ordering; drama must not reorder facts.

## Contract packaging

Phase 28 spec listed `packages/cinematic-contracts/**`. Per ADR 0002 (and the Phase 25 `replay-contracts` precedent), durable contracts live in:

- `packages/contracts-ts/src/cinematic.ts`
- `packages/contracts-python/src/aegis_contracts/cinematic.py`

UI orchestration lives in `apps/web/features/cinematic-replay/**`.

### Owned contracts (schemaVersion 1)

| Contract                   | Role                                  |
| -------------------------- | ------------------------------------- |
| `CinematicProvenanceV1`    | Beat → cursor/entity provenance       |
| `CameraDirectiveV1`        | Presentation-only camera instruction  |
| `CinematicBeatV1`          | Directed moment at a sequence         |
| `CinematicChapterV1`       | Ordered chapter over a sequence range |
| `PresentationHintV1`       | Safe scenario emphasis (no spoilers)  |
| `CinematicPlaybackStateV1` | Director session state                |
| `CinematicPlanV1`          | Deterministic plan bundle             |

## Scene-selection and choreography

Default beats are generated from important surfaces present in `ReplayStateV1`:

1. Establishing overview (seq 0)
2. Risk / early signal focus
3. Incident origin
4. Evidence / path trace
5. Agent investigation
6. Proposal focus
7. Approval moment
8. Consequence reveal
9. Report focus (when present)
10. Final overview

Silent Relay chapter labels come from `scenarios/operation-silent-relay/presentation/overview.md` and are applied as labels over sequences — not a second timeline.

Camera directives map to Phase 27 `CameraBookmark3D` + selection bridge (`selectedEntityId`). Missing entity refs are skipped with warnings; overview fallback is used when needed.

## Mode switching and synchronization

- **Normal replay** vs **Cinematic replay** toggle on `/replay/[runId]`.
- Switching modes preserves `ReplayCursorV1`, reconstructed state, and bookmarks.
- Director seeks via `setCursorSequence` so graph, timeline, inspector, and captions stay synchronized.
- Free-camera takeover pauses the director without mutating replay data; Resume returns to directed playback.
- “Open in 2D analysis” seeks the beat sequence and forces Sigma 2D.

## Accessibility and reduced motion

- Captions and chapter/beat lists remain available in `CinematicAccessibilityFallback`.
- Reduced motion disables continuous auto-advance and camera easing; operators step beats manually.
- WebGL `fallback2d` from Phase 27 still applies; cinematic meaning is preserved via text fallback.

## Performance and cleanup

- Plan generation for Silent Relay fixture size targets &lt; 250ms.
- Director clears interval timers on unmount/mode exit.
- Phase 27 adapter/R3F dispose lifecycle remains authoritative for WebGL resources.

## Failure modes

| Condition                                 | Behavior                                                              |
| ----------------------------------------- | --------------------------------------------------------------------- |
| Unavailable/malformed/incompatible replay | `CINEMATIC_REPLAY_UNAVAILABLE` / validation error; live run untouched |
| Missing entity in hint/beat               | Warning + skip entity; no invented nodes                              |
| Unsafe hint (hidden cause)                | Blocked by hint gating                                                |
| Incomplete early reconstruction           | Director seeks toward max sequence once to build a coherent plan      |

## Constraints Phase 29 must preserve

- Do not treat cinematic presentation as scoring truth or after-action authority.
- Keep Phase 25 reconstruction and Phase 26 cursor as the sole historical sources of truth.
- Do not reveal hidden causes through cinematic captions before the scoring experience owns that disclosure.
- Preserve reduced-motion and accessibility fallbacks.

## Development

```bash
NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web dev
# http://localhost:3000/replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
# Toggle Cinematic replay
```

Unit: `pnpm --filter @aegis/web exec vitest run features/cinematic-replay ../../tests/unit/cinematic-replay ../../tests/performance/cinematic-replay`

E2E: `CI=1 NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web exec playwright test tests/e2e/cinematic-replay.spec.ts`
