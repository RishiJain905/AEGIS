# Phase 26 Handoff — Replay Frontend

## Status

`READY FOR VALIDATION`

## Implemented

Mapped to Phase 26 spec Sections 7 and 18:

| Spec item | Implementation |
| --- | --- |
| Enter/exit historical mode, cursor, step, play/pause, speed, jump, bookmark, incident focus, return-to-live | `ReplayProvider`, `replay-store`, transport controls, keyboard hooks |
| Distinct historical state store | `apps/web/stores/replay-store.ts` isolated from live reducer |
| Historical graph/inspector/timeline/incidents/agents/proposals/run status | Replay shell + `ReplayVisualization` / `ReplayTimelineView` / `ReplayInspectorPanel` |
| Virtualize/filter timeline + sync selection | `TimelineFilterV1` + deduped audit marks sharing cursor |
| Two-cursor comparison | `ReplayComparisonPanel` → `GET .../diff` |
| Cancel stale reconstruction | `AbortController` + request generation |
| Keyboard, reduced motion, provenance, loading/unavailable/error | Banner, status extras, reduced-motion pause, structured errors |
| **AC1** Replay full detection-to-outcome sequence | Fixture/API reconstruct path + acceptance/e2e scrubbing |
| **AC2** Live and historical stores isolated | No `LiveRunProvider` on `/replay`; return-to-live clears store |
| **AC3** Graph and timeline share one replay cursor | Single `ReplayCursorV1` drives both |
| **AC4** Return-to-live authoritative catch-up | `ReturnToLiveResultV1` + navigate to `/runs/{runId}` |

**Explicitly not implemented:** Phase 27 Three.js, Phase 28 cinematic replay, Phase 29 scoring/after-action UX, production auth.

## Files added

| Path | Reason |
| --- | --- |
| `packages/contracts-ts/src/replay-frontend.ts` | Phase 26 Zod contracts |
| `packages/contracts-python/src/aegis_contracts/replay_frontend.py` | Phase 26 Pydantic contracts |
| `apps/web/stores/replay-store.ts` | Isolated historical store |
| `apps/web/features/replay/**` | Provider, shell, controls, bookmarks, comparison, inspector, visualization |
| `apps/web/features/timeline/replay/replay-timeline-view.tsx` | Historical timeline |
| `apps/web/fixtures/replay-fixture.ts` | Deterministic fixture projections for UI/e2e |
| `apps/web/scripts/capture-replay-frontend-demo.mjs` | Visual evidence harness |
| `tests/e2e/replay.spec.ts` | Playwright path |
| `tests/unit/replay-ui/acceptance.test.ts` | AC mapping |
| `docs/handoffs/26-replay-frontend-HANDOFF.md` | This handoff |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0027-replay-frontend.md` | ADR |
| `docs/frontend/replay-frontend.md` | Operator notes |
| Contract fixtures/schemas for 6 new contracts | Compatibility gate |

## Files modified

| Path | Reason |
| --- | --- |
| `apps/web/src/app/(shell)/replay/[runId]/page.tsx` | Replace stub with replay shell |
| `apps/web/lib/api/{types,production-client,fixture-client,query-keys}.ts` | Replay API methods |
| `packages/contracts-*/versioning` + exports/fixtures maps | Schema registration + `WORKSPACE_VERSION` |
| `packages/contracts-ts/src/replay.ts` | Export Phase 25 type aliases used by UI |
| `tests/e2e/shell.spec.ts` | Replay route assertion update |
| `apps/web/vitest.config.ts` | Include replay unit suites |
| Compatibility manifest | Hash/workspace bump |

## Files removed

None.

## Contracts introduced or changed

| Contract | Version | Notes |
| --- | --- | --- |
| `ReplayViewStateV1` | schema v1 | Historical/playback session |
| `ReplayBookmarkV1` | schema v1 | Named jump points |
| `ReplayComparisonV1` | schema v1 | Two-cursor comparison over `StateDiffV1` |
| `TimelineFilterV1` | schema v1 | Timeline filter/virtualization |
| `HistoricalGraphAdapterV1` | schema v1 | Read-only graph binding metadata |
| `ReturnToLiveResultV1` | schema v1 | Exit + authoritative resync required |
| `WORKSPACE_VERSION` | `0.0.0-phase26` | Compatibility bump |

No Phase 25 reconstruction contracts were semantically changed.

## Database migrations

None. Phase 25 snapshot tables remain authoritative.

## Environment and configuration changes

No new required env vars. Existing:

- `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture|api`
- `NEXT_PUBLIC_API_BASE_URL` for production replay API calls
- Phase 25 snapshot storage vars when exercising API-backed reconstruction

## Generated artifacts and fixtures

- `tests/contract/fixtures/valid/{replay_view_state,replay_bookmark,replay_comparison,timeline_filter,historical_graph_adapter,return_to_live_result}_v1.json`
- Matching generated schemas
- Visual evidence under `/opt/cursor/artifacts/screenshots/26-*.png` and `/opt/cursor/artifacts/videos/26-replay-frontend-motion.webm`

## Tests added

| Suite | Proves |
| --- | --- |
| `apps/web/stores/replay-store.test.ts` | Cursor clamp, stale cancel, isolation, bookmarks/comparison, return-to-live |
| `apps/web/features/replay/lib/*.test.ts` | Playback helpers, bookmark/dedupe |
| `apps/web/fixtures/replay-fixture.test.ts` | Domain progression, diffs, fail-closed errors |
| `tests/unit/replay-ui/acceptance.test.ts` | AC1–AC4 mapping |
| `tests/e2e/replay.spec.ts` | Open, scrub, play/speed, bookmarks, comparison, reload, error, keyboard/narrow, return-to-live |
| `pnpm check-contracts` | Cross-language fixture/schema parity |

## Commands executed and results

| Command | Result |
| --- | --- |
| `pnpm check-contracts` | **PASS** |
| `pnpm format:check` (Phase 26 paths) | **PASS** (workspace-wide still has pre-existing schema Prettier debt) |
| `pnpm lint` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm test` | **PASS** (web 76 tests including Phase 26) |
| `pnpm build` | **PASS** |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web test:e2e -- tests/e2e/replay.spec.ts` | **PASS** (8/8) |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture node apps/web/scripts/capture-replay-frontend-demo.mjs` | **PASS** — screenshots + recording captured |

Demo data source for visual evidence: fixture-backed Silent Relay-shaped reconstruction (`run_01ARZ3NDEKTSV4RRFFQ69G5FAV`) consuming the same contracts/API client surface as production. Production path uses Phase 25 `/api/v1/replay`.

## Architecture decisions and ADRs

- **Created:** [0027-replay-frontend.md](../AEGIS-v1.0-Agent-Specs/adrs/0027-replay-frontend.md) (Status: **Proposed**)
- No other ADRs superseded. ADR 0026 remains the reconstruction authority.
- Operator doc: [`docs/frontend/replay-frontend.md`](../frontend/replay-frontend.md)

## Known limitations

- Fixture-mode projections synthesize multi-domain progression for UI/e2e when API/Postgres are unavailable; production reconstruction remains Phase 25 server-side.
- Workspace-wide `pnpm format:check` may still fail on pre-existing regenerated schema JSON debt outside Phase 26 files.
- Graph canvas may be empty in headless capture environments without WebGL; keyboard-accessible node list and inspector still prove reconstructed state.
- Continuous playback is disabled under reduced motion by design.

## Deferred work

- Phase 27 Three.js semantic renderer
- Phase 28 cinematic incident replay
- Phase 29 scoring and after-action experience
- Production auth

## Risks for dependent phases

Phases 27–29 must preserve:

- Historical vs live isolation
- Sequence-primary shared cursor
- Phase 25 API as sole reconstruction source
- Return-to-live authoritative resync
- Distinct historical visual labeling
- No live mutation from replay controls

## Acceptance criteria evidence

| Criterion | Evidence |
| --- | --- |
| Users can replay the full detection-to-outcome sequence | Acceptance test AC1; e2e scrub start→later; screenshots early/later graph + timeline + inspector |
| Live and historical stores remain isolated | No `LiveRunProvider` on replay route; store clear on return-to-live; e2e return-to-live |
| Graph and timeline share one replay cursor | Shared store cursor; e2e scrub updates cursor label + inspector |
| Return-to-live performs safe authoritative catch-up | `ReturnToLiveResultV1`; e2e navigates to `/runs/{runId}` |

Visual evidence:

- `/opt/cursor/artifacts/screenshots/26-live-or-completed-run-available.png`
- `/opt/cursor/artifacts/screenshots/26-replay-route-historical-labeling.png`
- `/opt/cursor/artifacts/screenshots/26-replay-timeline-scrubbing-controls.png`
- `/opt/cursor/artifacts/screenshots/26-replay-play-pause-step-speed.png`
- `/opt/cursor/artifacts/screenshots/26-reconstructed-graph-early.png`
- `/opt/cursor/artifacts/screenshots/26-reconstructed-graph-later.png`
- `/opt/cursor/artifacts/screenshots/26-incident-timeline-synced-early.png`
- `/opt/cursor/artifacts/screenshots/26-incident-timeline-synced-later.png`
- `/opt/cursor/artifacts/screenshots/26-inspector-historical-state.png`
- `/opt/cursor/artifacts/screenshots/26-incident-bookmarks.png`
- `/opt/cursor/artifacts/screenshots/26-state-comparison.png`
- `/opt/cursor/artifacts/screenshots/26-safe-error-unavailable-replay.png`
- `/opt/cursor/artifacts/screenshots/26-responsive-narrow-layout.png`
- `/opt/cursor/artifacts/videos/26-replay-frontend-motion.webm`

## Prohibited-shortcut confirmation

- Production-path replay UI consumes Phase 25 APIs/contracts (not a frontend reconstruction engine)
- No Three.js / cinematic / scoring absorbed
- Live mutation paths are not invoked from replay controls
- Existing tests were not deleted or loosened to pass
- Validation commands above were executed in this environment
