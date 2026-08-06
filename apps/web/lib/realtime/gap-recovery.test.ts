import { describe, expect, it } from 'vitest';

import { EVENT_PAGE_LIMIT } from './catch-up';
import { MAX_DELTA_REPLAY_DISTANCE, planGapRecovery } from './gap-recovery';

describe('planGapRecovery', () => {
  it('has nothing to do when no sequence is missing', () => {
    expect(planGapRecovery({ fromSequence: 11, toSequence: 10 })).toMatchObject({
      strategy: 'none',
      distance: 0,
    });
  });

  it('counts a single missing sequence as a distance of one', () => {
    expect(planGapRecovery({ fromSequence: 11, toSequence: 11 })).toMatchObject({
      strategy: 'replay',
      distance: 1,
    });
  });

  it('replays a hole up to and including the cap', () => {
    const plan = planGapRecovery({
      fromSequence: 1,
      toSequence: MAX_DELTA_REPLAY_DISTANCE,
    });
    expect(plan).toMatchObject({
      strategy: 'replay',
      distance: MAX_DELTA_REPLAY_DISTANCE,
      fromSequence: 1,
      toSequence: MAX_DELTA_REPLAY_DISTANCE,
    });
  });

  it('goes to the snapshot one sequence past the cap', () => {
    // The boundary is the whole point: replaying is cheaper than a snapshot right up to it,
    // and steadily worse after it.
    expect(
      planGapRecovery({ fromSequence: 1, toSequence: MAX_DELTA_REPLAY_DISTANCE + 1 }).strategy,
    ).toBe('snapshot');
  });

  it('refuses to walk the tens of thousands of events a long-unattended run accumulates', () => {
    // The shape that produced the loop: forty paged reads that still finish short of the
    // head, leaving the cursor behind it so the next live event reads as another gap.
    const plan = planGapRecovery({ fromSequence: 1, toSequence: 50_000 });
    expect(plan.strategy).toBe('snapshot');
    expect(plan.distance).toBe(50_000);
  });

  it('honours an explicit cap, so callers with a different budget are not stuck with ours', () => {
    expect(planGapRecovery({ fromSequence: 1, toSequence: 5, maxReplayDistance: 4 }).strategy).toBe(
      'snapshot',
    );
    expect(planGapRecovery({ fromSequence: 1, toSequence: 4, maxReplayDistance: 4 }).strategy).toBe(
      'replay',
    );
  });

  it('keeps the cap to a handful of pages', () => {
    // A cap larger than a few pages is not a cap: it is the silent forty-page truncation
    // this planner replaced, wearing a name.
    expect(MAX_DELTA_REPLAY_DISTANCE % EVENT_PAGE_LIMIT).toBe(0);
    expect(MAX_DELTA_REPLAY_DISTANCE / EVENT_PAGE_LIMIT).toBeLessThanOrEqual(5);
  });
});
