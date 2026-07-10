# ADR 0029: Cinematic Incident Replay

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 28 requires directed camera chapters and presentation effects tied to authoritative replay events. Architecture rule 6 keeps Sigma.js as the primary analysis surface and Three.js as a derived presentation mode. Phase 25 owns reconstruction; Phase 26 owns the historical UI cursor; Phase 27 owns the semantic 3D renderer. The Phase 28 specification lists `packages/cinematic-contracts/**`, but ADR 0002 requires durable cross-language contracts to live in the shared contracts packages (the same adjustment used when Phase 25 mapped `packages/replay-contracts` into shared contracts).

## Decision

1. **Presentation over authority:** Cinematic replay is a presentation layer only. It consumes `ReplayStateV1` / `ReplayCursorV1` and drives Phase 27 `CameraBookmark3D` + selection. It must not invent domain facts or mutate live/authoritative replay data beyond cursor seeks already owned by Phase 26.

2. **Shared contract home:** Durable cinematic contracts (`CinematicBeatV1`, `CinematicChapterV1`, `CameraDirectiveV1`, `PresentationHintV1`, `CinematicPlaybackStateV1`, `CinematicProvenanceV1`, `CinematicPlanV1`) live in `packages/contracts-ts` and `packages/contracts-python` with schemaVersion 1 and compatibility fixtures. UI orchestration lives in `apps/web/features/cinematic-replay/**`.

3. **Deterministic beat planning:** Default beats are derived from important event/entity surfaces present in reconstructed state, ordered by `(sequence, priority, tieBreaker)`. Silent Relay chapters are labels over sequences, not a competing timeline.

4. **Safe presentation hints:** Scenario hints may emphasize known entities/captions but must set `revealsHiddenCause: false` and must not carry `hiddenCauseId`. Hint gating defers evidence-gated hints until evidence exists in replay state.

5. **Mode coexistence:** Normal replay and cinematic replay share one cursor. Free-camera takeover pauses the director without corrupting transport controls. “Open in 2D analysis” jumps to the beat’s sequence in Sigma.

6. **Accessibility:** Captions, chapter/beat lists, and reduced-motion static navigation preserve essential meaning without requiring 3D motion.

7. **Phase 29 boundary:** Scoring and final after-action experience remain Phase 29. Cinematic replay must not disclose hidden-cause scoring outcomes.

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| Separate `packages/cinematic-contracts` package | Conflicts with ADR 0002 single shared-contract home |
| Frontend-only reconstruction for cutscenes | Violates Phase 25/26 authority |
| Video recording / prerendered export | Explicitly out of scope; timeline is data reconstruction |
| Reveal hidden causes in captions for drama | Forbidden by presentation constraints; deferred to Phase 29 |

## Consequences

- Phase 28 adds shared cinematic contracts and a web feature module without a competing replay engine.
- Dependent Phase 29 work must preserve provenance-linked beats and must not treat cinematic captions as scoring authority.
- Visual evidence and e2e cover mode switching, sync, reduced motion, and fail-closed unavailable replay.

## Security and reliability

- No architecture non-negotiable rules are changed.
- Invalid/incomplete replay data fails closed with structured cinematic error codes.
- Camera/director cleanup clears timers; WebGL dispose remains Phase 27’s responsibility.
- No offensive capability introduced.

## Approval

- [ ] Project owner
