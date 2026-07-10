import { describe, expect, it } from 'vitest';

import { getReplayStateFixture } from '@/fixtures/replay-fixture';
import { planCinematicBeats } from '@/features/cinematic-replay/lib/beat-planner';
import {
  applyBeatCamera,
  beatIndexForSequence,
  chapterIndexForBeat,
  speedToBeatIntervalMs,
} from '@/features/cinematic-replay/lib/camera-director';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';

describe('camera director helpers', () => {
  it('maps beat index from replay sequence without reordering chronology', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    const index = beatIndexForSequence(plan, 180);
    const current = plan.beats[index];
    expect(current).toBeDefined();
    expect(current?.sequence).toBeLessThanOrEqual(180);
    const next = plan.beats[index + 1];
    if (next) {
      expect(next.sequence).toBeGreaterThan(180);
    }
  });

  it('applies camera bookmark and focus entity from directive', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    const incidentIndex = plan.beats.findIndex((b) => b.kind === 'incident_origin');
    const applied = applyBeatCamera(plan, incidentIndex);
    expect(applied).not.toBeNull();
    expect(applied?.camera.schemaVersion).toBe(1);
    expect(applied?.sequence).toBe(plan.beats[incidentIndex]?.sequence);
    expect((applied?.caption.length ?? 0) > 0).toBe(true);
  });

  it('exposes speed intervals for cinematic playback', () => {
    expect(speedToBeatIntervalMs('1x')).toBeGreaterThan(speedToBeatIntervalMs('2x'));
    expect(speedToBeatIntervalMs('4x')).toBeLessThan(speedToBeatIntervalMs('0.5x'));
  });
});

describe('cinematic replay store', () => {
  it('preserves plan when switching modes and supports free-camera takeover', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    const store = useCinematicReplayStore.getState();
    store.clear();
    store.setPlan(plan);
    store.setMode('cinematic');
    store.goToBeat(2);
    const beatBefore = useCinematicReplayStore.getState().beatIndex;
    store.setMode('normal');
    store.setMode('cinematic');
    expect(useCinematicReplayStore.getState().plan).not.toBeNull();
    expect(useCinematicReplayStore.getState().beatIndex).toBe(beatBefore);

    store.takeFreeCamera();
    expect(useCinematicReplayStore.getState().status).toBe('free_camera');
    store.resumeCinematic();
    expect(useCinematicReplayStore.getState().status).toBe('playing');

    const chapter = plan.chapters[0];
    expect(chapter).toBeDefined();
    const applied = store.goToChapter(0);
    expect(applied?.beat.chapterId).toBe(chapter?.id);
    if (applied) {
      expect(chapterIndexForBeat(plan, applied.beat)).toBe(0);
    }
  });

  it('cleans up to initial state', () => {
    useCinematicReplayStore.getState().clear();
    const state = useCinematicReplayStore.getState();
    expect(state.mode).toBe('normal');
    expect(state.plan).toBeNull();
    expect(state.lastApplied).toBeNull();
  });
});
