import { afterEach, describe, expect, it } from 'vitest';

import { TUTORIAL_PROGRESS_VERSION, type TutorialProgress } from './tutorial-contract';
import {
  armTutorial,
  clearActiveTutorialRunId,
  clearProgress,
  getActiveTutorialRunId,
  getArmToken,
  loadProgress,
  resumeTutorial,
  saveProgress,
  setActiveTutorialRunId,
  TUTORIAL_ARMED_EVENT,
} from './tutorial-storage';

const RUN_A = 'run_alpha';
const RUN_B = 'run_bravo';

function progress(overrides: Partial<TutorialProgress> = {}): TutorialProgress {
  return {
    version: TUTORIAL_PROGRESS_VERSION,
    cursor: 3,
    reached: 5,
    completedBeatIds: ['beat:one', 'beat:two'],
    skippedBeatIds: [],
    minimized: false,
    dismissed: false,
    clockHeld: false,
    ...overrides,
  };
}

afterEach(() => {
  window.localStorage.clear();
});

describe('tutorial-storage · progress', () => {
  it('round-trips a record and keeps runs independent', () => {
    saveProgress(RUN_A, progress());
    saveProgress(RUN_B, progress({ cursor: 0, reached: 0, completedBeatIds: [] }));

    expect(loadProgress(RUN_A)).toEqual(progress());
    expect(loadProgress(RUN_B).reached).toBe(0);
  });

  it('returns a fresh record for an unknown run', () => {
    expect(loadProgress('run_never_seen')).toEqual({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 0,
      reached: 0,
      completedBeatIds: [],
      skippedBeatIds: [],
      minimized: false,
      dismissed: false,
      clockHeld: false,
    });
  });

  it('discards progress written by a different schema version', () => {
    // The v1 shape: no cursor, a differently-modelled completion state. Reading it as if it
    // were current would drop the operator into a chapter they have never seen.
    window.localStorage.setItem(
      `aegis:tutorial:progress:${RUN_A}`,
      JSON.stringify({ reached: 6, welcomeAcknowledged: true, dismissed: false }),
    );
    expect(loadProgress(RUN_A)).toMatchObject({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 0,
      reached: 0,
      completedBeatIds: [],
    });
  });

  it('survives malformed JSON', () => {
    window.localStorage.setItem(`aegis:tutorial:progress:${RUN_A}`, '{not json');
    expect(loadProgress(RUN_A).cursor).toBe(0);
  });

  it('sanitises hostile field values rather than trusting them', () => {
    window.localStorage.setItem(
      `aegis:tutorial:progress:${RUN_A}`,
      JSON.stringify({
        version: TUTORIAL_PROGRESS_VERSION,
        cursor: -12,
        reached: 'nonsense',
        completedBeatIds: ['beat:one', 'beat:one', 42, null],
        skippedBeatIds: ['beat:two', 'beat:two', false],
        minimized: 'yes',
        dismissed: 1,
        clockHeld: 'true',
      }),
    );
    expect(loadProgress(RUN_A)).toEqual({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 0,
      reached: 0,
      completedBeatIds: ['beat:one'],
      skippedBeatIds: ['beat:two'],
      minimized: false,
      dismissed: false,
      clockHeld: false,
    });
  });

  it('upgrades a v2 record rather than restarting the operator mid-run', () => {
    // v3 added `clockHeld` and v4 added `skippedBeatIds`; the value of each for a record
    // written before it existed is exactly its default — so unlike v1, this upgrade is
    // lossless and discarding it would cost a mid-run operator their whole walkthrough.
    window.localStorage.setItem(
      `aegis:tutorial:progress:${RUN_A}`,
      JSON.stringify({
        version: 2,
        cursor: 11,
        reached: 14,
        completedBeatIds: ['beat:one'],
        minimized: false,
        dismissed: false,
      }),
    );
    expect(loadProgress(RUN_A)).toEqual({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 11,
      reached: 14,
      completedBeatIds: ['beat:one'],
      skippedBeatIds: [],
      minimized: false,
      dismissed: false,
      clockHeld: false,
    });
  });

  it('upgrades a v3 record, defaulting the not-yet-existing skippedBeatIds to empty', () => {
    window.localStorage.setItem(
      `aegis:tutorial:progress:${RUN_A}`,
      JSON.stringify({
        version: 3,
        cursor: 6,
        reached: 9,
        completedBeatIds: ['beat:one'],
        minimized: false,
        dismissed: false,
        clockHeld: true,
      }),
    );
    expect(loadProgress(RUN_A)).toEqual({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 6,
      reached: 9,
      completedBeatIds: ['beat:one'],
      skippedBeatIds: [],
      minimized: false,
      dismissed: false,
      clockHeld: true,
    });
  });

  it('never lets reached trail the cursor', () => {
    saveProgress(RUN_A, progress({ cursor: 7, reached: 2 }));
    expect(loadProgress(RUN_A).reached).toBe(7);
  });

  it('clears one run without touching another', () => {
    saveProgress(RUN_A, progress());
    saveProgress(RUN_B, progress());
    clearProgress(RUN_A);
    expect(loadProgress(RUN_A).cursor).toBe(0);
    expect(loadProgress(RUN_B).cursor).toBe(3);
  });
});

describe('tutorial-storage · active pointer', () => {
  it('arms a run with fresh progress', () => {
    saveProgress(RUN_A, progress({ dismissed: true }));
    armTutorial(RUN_A);
    expect(getActiveTutorialRunId()).toBe(RUN_A);
    expect(loadProgress(RUN_A)).toMatchObject({ cursor: 0, reached: 0, dismissed: false });
  });

  it('resumes a dismissed walkthrough without restarting it', () => {
    saveProgress(RUN_A, progress({ dismissed: true, minimized: true }));
    clearActiveTutorialRunId();

    resumeTutorial(RUN_A);

    expect(getActiveTutorialRunId()).toBe(RUN_A);
    expect(loadProgress(RUN_A)).toMatchObject({
      cursor: 3,
      reached: 5,
      completedBeatIds: ['beat:one', 'beat:two'],
      dismissed: false,
      minimized: false,
    });
  });

  it('ignores an empty run id', () => {
    armTutorial('');
    resumeTutorial('');
    expect(getActiveTutorialRunId()).toBeNull();
  });
});

describe('tutorial-storage · arm token', () => {
  it('advances on every arm and resume, so re-arming the same run is observable', () => {
    // The run id cannot signal a restart — the training run keeps its id — so the token is
    // the only thing that tells a mounted overlay to re-read.
    const start = getArmToken();

    armTutorial(RUN_A);
    const afterArm = getArmToken();
    expect(afterArm).toBeGreaterThan(start);

    armTutorial(RUN_A);
    expect(getArmToken()).toBeGreaterThan(afterArm);

    const beforeResume = getArmToken();
    resumeTutorial(RUN_A);
    expect(getArmToken()).toBeGreaterThan(beforeResume);
  });

  it('does not advance for pointer bookkeeping', () => {
    const before = getArmToken();
    setActiveTutorialRunId(RUN_B);
    saveProgress(RUN_B, progress());
    expect(getArmToken()).toBe(before);
  });

  it('stays monotonic when the stored value is missing or corrupt', () => {
    armTutorial(RUN_A);
    const armed = getArmToken();

    window.localStorage.removeItem('aegis:tutorial:arm-token');
    expect(getArmToken()).toBe(armed);

    window.localStorage.setItem('aegis:tutorial:arm-token', 'not-a-number');
    expect(getArmToken()).toBe(armed);
  });

  it('announces the arm on the window so a mounted overlay can re-read', () => {
    const seen: number[] = [];
    const listener = () => {
      seen.push(getArmToken());
    };
    window.addEventListener(TUTORIAL_ARMED_EVENT, listener);

    armTutorial(RUN_A);
    resumeTutorial(RUN_A);
    setActiveTutorialRunId(RUN_A);

    window.removeEventListener(TUTORIAL_ARMED_EVENT, listener);

    // Two events, and each listener call already sees the finished write.
    expect(seen).toHaveLength(2);
    expect(seen[1]).toBeGreaterThan(seen[0] ?? 0);
    expect(loadProgress(RUN_A).version).toBe(TUTORIAL_PROGRESS_VERSION);
  });
});
