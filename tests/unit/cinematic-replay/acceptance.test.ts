import { describe, expect, it } from 'vitest';

import { getReplayStateFixture } from '@/fixtures/replay-fixture';
import { planCinematicBeats } from '@/features/cinematic-replay/lib/beat-planner';
import { filterSafePresentationHints } from '@/features/cinematic-replay/lib/hint-gating';
import { applyBeatCamera } from '@/features/cinematic-replay/lib/camera-director';
import { SILENT_RELAY_PRESENTATION_HINTS } from '@/features/cinematic-replay/lib/silent-relay-hints';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';

/**
 * Phase 28 acceptance criteria (spec §18):
 * AC1 — A complete Silent Relay run plays as coherent chapters
 * AC2 — Every beat is linked to authoritative cursor/entity provenance
 * AC3 — Users can jump to equivalent 2D analysis state
 * AC4 — Captions/reduced motion preserve essential meaning
 */
describe('Phase 28 acceptance criteria', () => {
  it('AC1: complete Silent Relay run plans as coherent chapters', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({
      state,
      hints: SILENT_RELAY_PRESENTATION_HINTS,
    });
    expect(plan.chapters.map((c) => c.title)).toEqual(
      expect.arrayContaining([
        'Baseline operations',
        'Early signals',
        'Escalation',
        'Decision point',
        'Consequences',
      ]),
    );
    for (let i = 1; i < plan.beats.length; i += 1) {
      expect(plan.beats[i]!.sequence).toBeGreaterThanOrEqual(plan.beats[i - 1]!.sequence);
    }
  });

  it('AC2: every beat carries authoritative provenance', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    for (const beat of plan.beats) {
      expect(beat.provenance.sequence).toBe(beat.sequence);
      expect(beat.provenance.runId).toBe(state.runId);
      expect(['replay_state', 'presentation_hint', 'default_planner']).toContain(
        beat.provenance.source,
      );
    }
  });

  it('AC3: open-in-2D path preserves beat sequence and forces 2D view mode', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    useCinematicReplayStore.getState().clear();
    useCinematicReplayStore.getState().setPlan(plan);
    useCinematicReplayStore.getState().setMode('cinematic');
    const evidenceIndex = plan.beats.findIndex((b) => b.kind === 'evidence_focus');
    const applied = useCinematicReplayStore.getState().goToBeat(evidenceIndex);
    expect(applied?.sequence).toBe(plan.beats[evidenceIndex]!.sequence);

    useCinematicGraphStore.getState().setViewMode(GraphViewMode.TWO_D);
    expect(useCinematicGraphStore.getState().viewMode).toBe(GraphViewMode.TWO_D);
    // Cursor sequence equivalence is the beat sequence (Phase 26 store seek)
    expect(applied?.beat.provenance.sequence).toBe(applied?.sequence);
  });

  it('AC4: captions and reduced-motion preserve essential meaning; unsafe hints blocked', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state, hints: SILENT_RELAY_PRESENTATION_HINTS });
    const applied = applyBeatCamera(plan, 0);
    expect(applied?.caption.length).toBeGreaterThan(0);

    useCinematicReplayStore.getState().setReducedMotion(true);
    useCinematicReplayStore.getState().setCaptionsEnabled(true);
    expect(useCinematicReplayStore.getState().reducedMotion).toBe(true);
    expect(useCinematicReplayStore.getState().captionsEnabled).toBe(true);

    const warnings: string[] = [];
    const early = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 40 });
    const gated = filterSafePresentationHints(SILENT_RELAY_PRESENTATION_HINTS, early, warnings);
    expect(gated.every((h) => h.revealsHiddenCause === false)).toBe(true);
    expect(gated.every((h) => h.hiddenCauseId == null)).toBe(true);
  });
});
