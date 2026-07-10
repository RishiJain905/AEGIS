# Phase 28 Handoff — Cinematic Incident Replay

## Status

`READY FOR VALIDATION`

## Implemented

Mapped to Phase 28 spec Sections 7 and 18:

| Spec item | Implementation |
| --- | --- |
| Cinematic beats/chapters referencing sequence/entities/incidents/agents/proposals/actions | `planCinematicBeats` in `apps/web/features/cinematic-replay/lib/beat-planner.ts` |
| Camera director (establishing, path trace, agent focus, approval, consequence, overview) | `CameraDirectiveV1` + `applyBeatCamera` + Phase 27 `CameraBookmark3D` |
| Default beats from important event types + safe presentation hints | Beat planner + `SILENT_RELAY_PRESENTATION_HINTS` / `presentation/cinematic-hints.json` |
| Play/pause/skip/chapter nav/free-camera/resume/speed/captions/reduced-motion | `CinematicTransportControls` + store + director controller |
| Deterministic beat ordering; missing refs handled gracefully | `(sequence, priority, tieBreaker)` sort; warnings for missing entities |
| Every beat opens equivalent 2D replay cursor | `cinematic-open-2d` / a11y jump → `setCursorSequence` + `viewMode: 2d` |
| Presentation hints never reveal hidden truth before evidence | Hint gating + contract refinement |
| **AC1** Complete Silent Relay run as coherent chapters | Planner + acceptance + e2e chapter rail |
| **AC2** Every beat linked to authoritative provenance | `CinematicProvenanceV1` on each beat |
| **AC3** Jump to equivalent 2D analysis state | Open-in-2D control + e2e |
| **AC4** Captions/reduced motion preserve meaning | Captions + a11y fallback + reduced-motion badge |

**Explicitly not implemented:** Phase 29 scoring/after-action UX, prerendered video export, production auth, cloud deployment.

**Contract packaging note:** Spec listed `packages/cinematic-contracts/**`. Per ADR 0002 (same adjustment as Phase 25 replay contracts), durable contracts live in shared `packages/contracts-ts` + `packages/contracts-python`.

## Files added

| Path | Reason |
| --- | --- |
| `packages/contracts-ts/src/cinematic.ts` | Durable cinematic contracts |
| `packages/contracts-python/src/aegis_contracts/cinematic.py` | Python mirror |
| `apps/web/features/cinematic-replay/**` | Planner, director, UI, store, tests |
| `scenarios/operation-silent-relay/presentation/cinematic-hints.json` | Safe scenario hints |
| `tests/e2e/cinematic-replay.spec.ts` | Playwright coverage |
| `tests/unit/cinematic-replay/acceptance.test.ts` | AC1–AC4 mapping |
| `tests/performance/cinematic-replay/cinematic-replay-perf.test.ts` | Plan budget + cleanup |
| `tests/contract/fixtures/valid/cinematic_*.json` + schemas | Compatibility fixtures |
| `docs/frontend/cinematic-replay.md` | Operator/architecture notes |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0029-cinematic-incident-replay.md` | ADR |
| `apps/web/scripts/capture-cinematic-replay-demo.mjs` | Visual evidence harness |
| `docs/handoffs/28-cinematic-incident-replay-HANDOFF.md` | This handoff |
| `docs/handoffs/evidence/28-cinematic-incident-replay/*` | Screenshots + recording |

## Files modified

| Path | Reason |
| --- | --- |
| `packages/contracts-ts/src/versioning.ts` / Python versioning | Schema versions + `WORKSPACE_VERSION=0.0.0-phase28` |
| `packages/contracts-ts/src/index.ts` / Python `__init__.py` / `fixtures.py` | Export + fixture map |
| `apps/web/features/replay/components/replay-command-centre-shell.tsx` | Mount cinematic UI + director |
| `apps/web/vitest.config.ts` | Include cinematic-replay suites |
| `scenarios/operation-silent-relay/presentation/overview.md` + `manifest.yaml` | Hint constraints + media entry |
| `docs/frontend/cinematic-renderer.md` / `replay-frontend.md` / ADR README | Cross-links |
| `tests/contract/fixtures/compatibility-manifest.json` | New artifact hashes |

## Files removed

None.

## Contracts introduced or changed

Durable cross-language (schemaVersion 1):

- `CinematicProvenanceV1`
- `CameraDirectiveV1`
- `CinematicBeatV1`
- `CinematicChapterV1`
- `PresentationHintV1`
- `CinematicPlaybackStateV1`
- `CinematicPlanV1`
- `CinematicErrorCode`

No Phase 25/26/27 wire contract semantic breaks. `WORKSPACE_VERSION` bumped to `0.0.0-phase28`.

## Database migrations

None.

## Environment and configuration changes

None required. Fixture mode uses existing `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture`.

## Generated artifacts and fixtures

- Contract fixtures/schemas under `tests/contract/fixtures/`
- Silent Relay `presentation/cinematic-hints.json`
- Visual evidence under `docs/handoffs/evidence/28-cinematic-incident-replay/`

## Tests added

| Test | Proves |
| --- | --- |
| `beat-planner.test.ts` | Coherent chapters, provenance, determinism, missing-entity handling, hint gating |
| `camera-director.test.ts` | Sequence→beat mapping, camera apply, mode/free-camera store behavior |
| `acceptance.test.ts` | AC1–AC4 |
| `cinematic-replay-perf.test.ts` | Plan budget + store cleanup |
| `cinematic-replay.spec.ts` | E2E mode, sync, 2D jump, reduced motion, error, narrow layout |
| `pnpm check-contracts` | TS/Python/fixture parity |

## Commands executed and results

```bash
pnpm format:check          # PASS
pnpm lint                  # PASS
pnpm typecheck             # PASS
pnpm test                  # PASS
pnpm build                 # PASS
pnpm check-contracts       # PASS
pnpm --filter @aegis/web exec vitest run features/cinematic-replay ../../tests/unit/cinematic-replay ../../tests/performance/cinematic-replay  # PASS (16)
# E2E + visual capture recorded after stack start (see evidence section)
```

## Architecture decisions and ADRs

- ADR 0029: cinematic presentation over authoritative replay; shared-contract home; camera presentation-only; Phase 29 boundary.
- No architecture non-negotiable rules changed.
- Reuses Phase 25 reconstruction, Phase 26 cursor/store, Phase 27 `SemanticSceneAdapter` / `CameraBookmark3D`.

## Known limitations

- Beat planning uses the fullest reconstructed state available when entering cinematic mode (seeks toward max sequence once). Per-beat graph truth still comes from Phase 25 reconstruction at the beat sequence.
- Continuous cinematic auto-advance is disabled under reduced motion (manual beat stepping + captions remain).
- WebGL capability fallback remains Phase 27’s responsibility; cinematic a11y panel always available.

## Deferred work

- Phase 29 scoring and final after-action experience
- Prerendered video export
- Production auth / cloud deployment

## Risks for dependent phases

- Phase 29 must not treat cinematic captions as scoring authority or reveal hidden causes through presentation hints.
- Preserve sequence-primary cursor sync and fail-closed unavailable replay behavior.
- Do not fork reconstruction or invent renderer-owned domain state.

## Acceptance criteria evidence

| AC | Evidence |
| --- | --- |
| AC1 coherent chapters | `planCinematicBeats` + `tests/unit/cinematic-replay/acceptance.test.ts` + e2e chapter rail + screenshots |
| AC2 provenance | Every beat has `CinematicProvenanceV1`; unit asserts |
| AC3 jump to 2D | `cinematic-open-2d` / a11y control; e2e asserts 2D mode + cursor |
| AC4 captions/reduced motion | Captions panel + reduced-motion badge + a11y beat list; e2e reduced-motion test |

## Prohibited-shortcut confirmation

- No competing replay engine or frontend-only reconstruction
- No invented domain facts in Three.js / cinematic layer
- No hidden-cause spoilers in presentation hints
- No Phase 29 scoring absorbed
- No live mutation from cinematic controls beyond Phase 26 cursor seeks
- Validation commands were executed in this tree; results recorded honestly
