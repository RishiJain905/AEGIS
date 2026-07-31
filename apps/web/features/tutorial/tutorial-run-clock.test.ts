import { describe, expect, it } from 'vitest';

import { flattenChapters } from './tutorial-machine';
import { TUTORIAL_CHAPTERS } from './tutorial-content';
import {
  INITIAL_PROGRESS,
  type ResolvedBeat,
  type TutorialEvidenceKey,
  type TutorialProgress,
} from './tutorial-contract';
import {
  HOLD_AT_ELAPSED_SIM_SECONDS,
  RUN_ENDED_NOTICE,
  RUN_HELD_NOTICE,
  SIM_HORIZON_SECONDS,
  SIM_INITIAL_TIME_ISO,
  UNREACHABLE_OBJECTIVE_PENDING,
  applyRunClockNotice,
  elapsedSimSeconds,
  isRunTerminal,
  runClockNotice,
  setClockHeld,
  shouldHoldRunClock,
  shouldWatchRunClock,
  walkthroughNeedsLiveRun,
  withRunClockNotice,
} from './tutorial-run-clock';

const BEATS = flattenChapters(TUTORIAL_CHAPTERS);

/** An absolute sim clock `seconds` into the run, the way the API reports it. */
function simTimeAt(seconds: number): string {
  return new Date(Date.parse(SIM_INITIAL_TIME_ISO) + seconds * 1000).toISOString();
}

function progress(overrides: Partial<TutorialProgress> = {}): TutorialProgress {
  return { ...INITIAL_PROGRESS, completedBeatIds: [], ...overrides };
}

/** The beat carrying a given objective. Throws rather than asserting, so content drift is loud. */
function beatFor(evidence: TutorialEvidenceKey): ResolvedBeat {
  const found = BEATS.find((candidate) => candidate.beat.objective?.evidence === evidence);
  if (!found) {
    throw new Error(`content no longer has a ${evidence} objective`);
  }
  return found;
}

function firstBeat(): ResolvedBeat {
  const found = BEATS[0];
  if (!found) {
    throw new Error('content has no beats');
  }
  return found;
}

/** The beat whose objective is the run finishing — the walkthrough's release point. */
function releaseBeat(): ResolvedBeat {
  return beatFor('runComplete');
}

/** A hold input that would fire, so each test can negate exactly one thing. */
function holdInput(overrides: Partial<Parameters<typeof shouldHoldRunClock>[0]> = {}) {
  return {
    walkthroughActive: true,
    needsLiveRun: true,
    clockHeld: false,
    runStatus: 'running',
    simTime: simTimeAt(HOLD_AT_ELAPSED_SIM_SECONDS),
    ...overrides,
  };
}

describe('elapsedSimSeconds', () => {
  it('measures virtual time from the engine epoch', () => {
    expect(elapsedSimSeconds(SIM_INITIAL_TIME_ISO)).toBe(0);
    expect(elapsedSimSeconds(simTimeAt(1200))).toBe(1200);
  });

  it('refuses to guess from a clock it does not understand', () => {
    expect(elapsedSimSeconds(null)).toBeNull();
    expect(elapsedSimSeconds('')).toBeNull();
    expect(elapsedSimSeconds('not a timestamp')).toBeNull();
    // Behind the epoch, and implausibly far past it: a scenario with its own initial clock.
    expect(elapsedSimSeconds('2025-12-31T23:00:00.000Z')).toBeNull();
    expect(elapsedSimSeconds('2027-01-01T00:00:00.000Z')).toBeNull();
  });
});

describe('the hold threshold', () => {
  it('sits inside the horizon, after the training narrative has played out', () => {
    expect(HOLD_AT_ELAPSED_SIM_SECONDS).toBeLessThan(SIM_HORIZON_SECONDS);
    // The scenario's last scripted event fires at 00:07:00 of virtual time.
    expect(HOLD_AT_ELAPSED_SIM_SECONDS).toBeGreaterThan(7 * 60);
  });
});

describe('shouldHoldRunClock', () => {
  it('holds a training run that is closing on its horizon', () => {
    expect(shouldHoldRunClock(holdInput())).toBe(true);
    expect(shouldHoldRunClock(holdInput({ simTime: simTimeAt(SIM_HORIZON_SECONDS - 1) }))).toBe(
      true,
    );
  });

  it('leaves a run alone until it is near the horizon', () => {
    expect(shouldHoldRunClock(holdInput({ simTime: simTimeAt(0) }))).toBe(false);
    expect(
      shouldHoldRunClock(holdInput({ simTime: simTimeAt(HOLD_AT_ELAPSED_SIM_SECONDS - 1) })),
    ).toBe(false);
  });

  it('is inert for anything that is not an armed training walkthrough', () => {
    expect(shouldHoldRunClock(holdInput({ walkthroughActive: false }))).toBe(false);
  });

  it('holds at most once, so a manual resume is never fought', () => {
    expect(shouldHoldRunClock(holdInput({ clockHeld: true }))).toBe(false);
    // Even deep past the threshold, with the run running again after the operator resumed.
    expect(
      shouldHoldRunClock(
        holdInput({ clockHeld: true, simTime: simTimeAt(SIM_HORIZON_SECONDS - 1) }),
      ),
    ).toBe(false);
  });

  it('respects a run that is already paused, not yet started, or already terminal', () => {
    for (const runStatus of ['paused', 'created', 'stopped', 'completed', null]) {
      expect(shouldHoldRunClock(holdInput({ runStatus }))).toBe(false);
    }
  });

  it('does not hold once the walkthrough wants the run to finish', () => {
    expect(shouldHoldRunClock(holdInput({ needsLiveRun: false }))).toBe(false);
  });

  it('does nothing when the clock cannot be read', () => {
    expect(shouldHoldRunClock(holdInput({ simTime: null }))).toBe(false);
    expect(shouldHoldRunClock(holdInput({ simTime: 'garbage' }))).toBe(false);
  });
});

describe('walkthroughNeedsLiveRun', () => {
  it('needs the run through the cockpit chapters', () => {
    expect(walkthroughNeedsLiveRun(progress({ reached: 0 }), BEATS)).toBe(true);
    expect(walkthroughNeedsLiveRun(progress({ reached: releaseBeat().index - 1 }), BEATS)).toBe(
      true,
    );
  });

  it('releases the run at the beat that asks for it to finish, and after', () => {
    const release = releaseBeat();
    expect(walkthroughNeedsLiveRun(progress({ reached: release.index }), BEATS)).toBe(false);
    expect(walkthroughNeedsLiveRun(progress({ reached: BEATS.length - 1 }), BEATS)).toBe(false);
  });

  it('falls back to "until the end" when no beat asks for a finished run', () => {
    const withoutRelease = BEATS.filter(
      (candidate) => candidate.beat.objective?.evidence !== 'runComplete',
    );
    expect(walkthroughNeedsLiveRun(progress({ reached: 0 }), withoutRelease)).toBe(true);
    expect(
      walkthroughNeedsLiveRun(progress({ reached: withoutRelease.length - 1 }), withoutRelease),
    ).toBe(false);
    expect(walkthroughNeedsLiveRun(progress(), [])).toBe(false);
  });
});

describe('shouldWatchRunClock', () => {
  it('watches while the hold is still available', () => {
    expect(
      shouldWatchRunClock({
        walkthroughActive: true,
        needsLiveRun: true,
        clockHeld: false,
        pendingKeys: [],
      }),
    ).toBe(true);
  });

  it('keeps watching after the hold when a simulation-fed objective is outstanding', () => {
    expect(
      shouldWatchRunClock({
        walkthroughActive: true,
        needsLiveRun: true,
        clockHeld: true,
        pendingKeys: ['alertRaised'],
      }),
    ).toBe(true);
  });

  it('stands down when nothing left can turn on the run clock', () => {
    expect(
      shouldWatchRunClock({
        walkthroughActive: true,
        needsLiveRun: false,
        clockHeld: true,
        pendingKeys: ['assetSelected', 'incidentOpened'],
      }),
    ).toBe(false);
    expect(
      shouldWatchRunClock({
        walkthroughActive: false,
        needsLiveRun: true,
        clockHeld: false,
        pendingKeys: ['alertRaised'],
      }),
    ).toBe(false);
  });
});

describe('isRunTerminal', () => {
  it('recognises the statuses past which nothing more happens', () => {
    expect(isRunTerminal('stopped')).toBe(true);
    expect(isRunTerminal('completed')).toBe(true);
    expect(isRunTerminal('running')).toBe(false);
    expect(isRunTerminal('paused')).toBe(false);
    expect(isRunTerminal(null)).toBe(false);
  });
});

describe('runClockNotice', () => {
  it('says nothing about a healthy run', () => {
    expect(
      runClockNotice({ runStatus: 'running', clockHeld: false, pendingKeys: ['alertRaised'] }),
    ).toBeNull();
  });

  it('explains a run this walkthrough held, only while it is still held', () => {
    expect(runClockNotice({ runStatus: 'paused', clockHeld: true, pendingKeys: [] })).toBe('held');
    // The operator resumed: the explanation stops following them around.
    expect(runClockNotice({ runStatus: 'running', clockHeld: true, pendingKeys: [] })).toBeNull();
    // A run the operator paused themselves is not ours to narrate.
    expect(runClockNotice({ runStatus: 'paused', clockHeld: false, pendingKeys: [] })).toBeNull();
  });

  it('explains an ended run that stranded an objective', () => {
    expect(
      runClockNotice({ runStatus: 'stopped', clockHeld: true, pendingKeys: ['proposalRaised'] }),
    ).toBe('ended');
  });

  it('stays quiet when a finished run cost the operator nothing', () => {
    // Past "Play it out": the run ending is the payoff, and only cockpit objectives remain.
    expect(
      runClockNotice({ runStatus: 'stopped', clockHeld: false, pendingKeys: ['reportReady'] }),
    ).toBeNull();
    expect(runClockNotice({ runStatus: 'completed', clockHeld: true, pendingKeys: [] })).toBeNull();
  });
});

describe('applyRunClockNotice', () => {
  const learnBeat = firstBeat().beat;
  const strandedBeat = beatFor('alertExplanationOpened').beat;
  const cockpitBeat = beatFor('assetSelected').beat;

  it('is identity-preserving when there is nothing to say', () => {
    expect(applyRunClockNotice(learnBeat, null)).toBe(learnBeat);
    expect(withRunClockNotice(firstBeat(), null)).toBe(firstBeat());
  });

  it('appends the hold explanation without touching the beat itself', () => {
    const held = applyRunClockNotice(learnBeat, 'held');
    expect(held.body).toEqual([...learnBeat.body, RUN_HELD_NOTICE]);
    expect(held.title).toBe(learnBeat.title);
    expect(held.anchors).toEqual(learnBeat.anchors);
    expect(learnBeat.body).not.toContain(RUN_HELD_NOTICE);
  });

  it('marks an objective the ended run can no longer satisfy', () => {
    const ended = applyRunClockNotice(strandedBeat, 'ended');
    expect(ended.body).toContain(RUN_ENDED_NOTICE);
    expect(ended.objective?.pending).toBe(UNREACHABLE_OBJECTIVE_PENDING);
    // The confirmation copy is untouched: an objective met before the run ended still reads met.
    expect(ended.objective?.done).toBe(strandedBeat.objective?.done);
  });

  it('leaves objectives a finished run does not block alone', () => {
    const ended = applyRunClockNotice(cockpitBeat, 'ended');
    expect(ended.body).toContain(RUN_ENDED_NOTICE);
    expect(ended.objective?.pending).toBe(cockpitBeat.objective?.pending);
  });

  it('keeps the beat id stable so progress and test hooks survive the notice', () => {
    expect(withRunClockNotice(firstBeat(), 'held').beat.id).toBe(firstBeat().beat.id);
    expect(withRunClockNotice(firstBeat(), 'held').index).toBe(firstBeat().index);
  });
});

describe('setClockHeld', () => {
  it('records the spent hold and preserves identity when it already holds', () => {
    const before = progress();
    const after = setClockHeld(before, true);
    expect(after.clockHeld).toBe(true);
    expect(setClockHeld(after, true)).toBe(after);
    expect(setClockHeld(before, false)).toBe(before);
  });
});
