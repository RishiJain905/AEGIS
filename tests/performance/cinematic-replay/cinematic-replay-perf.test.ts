import { describe, expect, it } from 'vitest';

import { getReplayStateFixture } from '@/fixtures/replay-fixture';
import { planCinematicBeats } from '@/features/cinematic-replay/lib/beat-planner';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';

describe('cinematic replay performance and cleanup', () => {
  it('plans Silent Relay target size within budget', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const started = performance.now();
    const plan = planCinematicBeats({ state });
    const elapsed = performance.now() - started;
    expect(plan.beats.length).toBeGreaterThan(0);
    expect(elapsed).toBeLessThan(250);
  });

  it('clears store timers/state on dispose-equivalent clear()', () => {
    const state = getReplayStateFixture('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', { sequence: 500 });
    const plan = planCinematicBeats({ state });
    useCinematicReplayStore.getState().setPlan(plan);
    useCinematicReplayStore.getState().setMode('cinematic');
    useCinematicReplayStore.getState().setStatus('playing');
    useCinematicReplayStore.getState().clear();
    const after = useCinematicReplayStore.getState();
    expect(after.plan).toBeNull();
    expect(after.status).toBe('idle');
    expect(after.mode).toBe('normal');
    expect(after.lastApplied).toBeNull();
  });
});
