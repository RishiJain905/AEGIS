# Replay Frontend (Phase 26)

## Route

- Historical: `/replay/{runId}`
- Live: `/runs/{runId}`

Replay never mounts the live WebSocket provider.

## Lifecycle

1. Enter historical mode → load latest reconstructable range → set shared cursor
2. Scrub / step / play → cancel stale requests → `GET /api/v1/replay/runs/{runId}/state?sequence=`
3. Render reconstructed graph, timeline, incidents, evidence, proposals, approvals, reports
4. Return to live → clear replay store → navigate to `/runs/{runId}` for authoritative bootstrap

## Cursor and controls

- Sequence-primary cursor shared by graph + timeline + inspector
- Play / pause / step ±1 / speed `0.5x|1x|2x|4x`
- Reduced motion disables continuous playback; discrete step/scrub remain
- Keyboard: Space, ←/→, Home/End, [/], B (next bookmark)

## Bookmarks and comparison

- Bookmarks derived from incidents, snapshot manifests, and notable audit events
- Comparison marks left/right sequences and loads `StateDiffV1`

## Visual rules

- Persistent “Historical replay — read-only” banner
- Provenance and applied event range always visible when available
- Live transport controls hidden
- Approval mutations disabled

## Failure modes

Unavailable / corrupt / incompatible replay data surfaces actionable codes (`REPLAY_NOT_FOUND`, `SNAPSHOT_*`) without mutating live state.

## Deferred

Phase 27 Three.js semantic renderer, Phase 28 cinematic incident replay, Phase 29 scoring/after-action UX.
