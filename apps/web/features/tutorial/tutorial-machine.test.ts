import { describe, expect, it } from 'vitest';

import {
  EMPTY_EVIDENCE,
  INITIAL_PROGRESS,
  TUTORIAL_PROGRESS_VERSION,
  type TutorialBeat,
  type TutorialChapter,
  type TutorialEvidence,
  type TutorialProgress,
} from './tutorial-contract';
import {
  applyEvidence,
  clampProgress,
  flattenChapters,
  goBack,
  goNext,
  isObjectiveSatisfied,
  isWalkthroughComplete,
  jumpToChapter,
  objectiveAudit,
  objectiveBlockReason,
  pendingObjectiveKeys,
  resolveCurrentBeat,
  setDismissed,
  setMinimized,
  skipChapter,
  skipObjective,
} from './tutorial-machine';

/**
 * The machine is content-agnostic, so these tests run on a fixture rather than the real
 * walkthrough: the rules under test must hold for any chapter/beat arrangement, and a copy
 * edit in `tutorial-content` must never turn this suite red.
 *
 * Fixture shape (indices in brackets):
 *   ch-one   [0] welcome (learn)
 *            [1] watch   (do · telemetryFlowing · auto-advance)
 *            [2] alert   (do · alertRaised)
 *   ch-two   [3] brief   (learn)
 *            [4] open    (do · incidentOpened · auto-advance)
 *   ch-tour  [5] report  (do · reportReady)
 */
const CHAPTERS: readonly TutorialChapter[] = [
  {
    id: 'ch-one',
    title: 'Chapter one',
    summary: 'First',
    section: 'cockpit',
    beats: [
      {
        id: 'welcome',
        kind: 'learn',
        title: 'Welcome',
        body: [],
        anchors: [],
        pointerLabel: 'shell',
        primaryAction: 'begin',
      },
      {
        id: 'watch',
        kind: 'do',
        title: 'Watch',
        body: [],
        anchors: [],
        pointerLabel: 'timeline',
        objective: {
          evidence: 'telemetryFlowing',
          pending: 'Wait for telemetry',
          done: 'Telemetry is flowing',
          advanceOnSatisfied: true,
          requirement: 'required',
        },
      },
      {
        id: 'alert',
        kind: 'do',
        title: 'Alert',
        body: [],
        anchors: [],
        pointerLabel: 'alerts',
        objective: {
          evidence: 'alertRaised',
          pending: 'Wait for an alert',
          done: 'Alert raised',
          requirement: 'required',
        },
      },
    ],
  },
  {
    id: 'ch-two',
    title: 'Chapter two',
    summary: 'Second',
    section: 'cockpit',
    beats: [
      {
        id: 'brief',
        kind: 'learn',
        title: 'Brief',
        body: [],
        anchors: [],
        pointerLabel: 'incidents',
      },
      {
        id: 'open',
        kind: 'do',
        title: 'Open',
        body: [],
        anchors: [],
        pointerLabel: 'incidents',
        objective: {
          evidence: 'incidentOpened',
          pending: 'Open an incident',
          done: 'Incident open',
          advanceOnSatisfied: true,
          requirement: 'required',
        },
      },
    ],
  },
  {
    id: 'ch-tour',
    title: 'Tour',
    summary: 'Third',
    section: 'tour',
    beats: [
      {
        id: 'report',
        kind: 'do',
        title: 'Report',
        body: [],
        anchors: [],
        pointerLabel: 'reports',
        objective: {
          evidence: 'reportReady',
          pending: 'Wait for it',
          done: 'Ready',
          requirement: 'skippable',
          skipReason: 'Report generation can stall.',
        },
      },
    ],
  },
];

const BEATS = flattenChapters(CHAPTERS);

const WELCOME = 0;
const WATCH = 1;
const ALERT = 2;
const BRIEF = 3;
const OPEN = 4;
const REPORT = 5;

function progressAt(overrides: Partial<TutorialProgress> = {}): TutorialProgress {
  return { ...INITIAL_PROGRESS, completedBeatIds: [], ...overrides };
}

function beatAt(index: number): TutorialBeat {
  const resolved = BEATS[index];
  if (!resolved) {
    throw new Error(`fixture has no beat at index ${String(index)}`);
  }
  return resolved.beat;
}

function evidence(overrides: Partial<TutorialEvidence>): TutorialEvidence {
  return { ...EMPTY_EVIDENCE, ...overrides };
}

describe('flattenChapters', () => {
  it('numbers beats within their chapter and indexes them across the walkthrough', () => {
    expect(BEATS).toHaveLength(6);
    expect(BEATS.map((resolved) => resolved.beat.id)).toEqual([
      'welcome',
      'watch',
      'alert',
      'brief',
      'open',
      'report',
    ]);

    expect(BEATS[OPEN]).toMatchObject({
      index: OPEN,
      beatNumber: 2,
      beatCount: 2,
      chapterNumber: 2,
      chapterCount: 3,
    });
    expect(BEATS[OPEN]?.chapter.id).toBe('ch-two');
  });

  it('returns an empty list for empty content', () => {
    expect(flattenChapters([])).toEqual([]);
  });
});

describe('isObjectiveSatisfied', () => {
  it('reads the beat objective out of the evidence snapshot', () => {
    const beat = beatAt(ALERT);
    expect(isObjectiveSatisfied(beat, EMPTY_EVIDENCE)).toBe(false);
    expect(isObjectiveSatisfied(beat, evidence({ alertRaised: true }))).toBe(true);
  });

  it('is never satisfied for a learn beat, which has no objective', () => {
    const learn = beatAt(WELCOME);
    expect(
      isObjectiveSatisfied(learn, evidence({ telemetryFlowing: true, alertRaised: true })),
    ).toBe(false);
  });
});

describe('goNext · soft gating', () => {
  it('advances even though the current objective is unmet', () => {
    const start = progressAt({ cursor: WATCH, reached: WATCH });
    const next = goNext(start, BEATS);
    expect(next.cursor).toBe(ALERT);
    expect(next.completedBeatIds).toEqual([]);
  });

  it('clamps at the final beat and preserves identity there', () => {
    const end = progressAt({ cursor: REPORT, reached: REPORT });
    expect(goNext(end, BEATS)).toBe(end);
  });

  it('raises reached monotonically', () => {
    let progress = progressAt();
    progress = goNext(progress, BEATS);
    progress = goNext(progress, BEATS);
    expect(progress).toMatchObject({ cursor: ALERT, reached: ALERT });
  });
});

describe('goBack', () => {
  it('moves the cursor without lowering reached', () => {
    const start = progressAt({ cursor: OPEN, reached: OPEN });
    const back = goBack(goBack(start));
    expect(back).toMatchObject({ cursor: ALERT, reached: OPEN });
  });

  it('stops at the first beat and preserves identity there', () => {
    const start = progressAt();
    expect(goBack(start)).toBe(start);
  });

  it('lets the operator return to where they were after stepping back', () => {
    const start = progressAt({ cursor: OPEN, reached: OPEN });
    const forward = goNext(goBack(start), BEATS);
    expect(forward).toMatchObject({ cursor: OPEN, reached: OPEN });
  });
});

describe('skipChapter', () => {
  it('lands on the first beat of the next chapter', () => {
    const start = progressAt({ cursor: WATCH, reached: WATCH });
    expect(skipChapter(start, BEATS)).toMatchObject({ cursor: BRIEF, reached: BRIEF });
  });

  it('skips from anywhere in a chapter, not just its first beat', () => {
    const start = progressAt({ cursor: BRIEF, reached: BRIEF });
    expect(skipChapter(start, BEATS).cursor).toBe(REPORT);
  });

  it('lands on the last beat when there is no next chapter', () => {
    const start = progressAt({ cursor: REPORT, reached: REPORT });
    expect(skipChapter(start, BEATS)).toBe(start);
  });
});

describe('jumpToChapter', () => {
  it('moves to the first beat of the named chapter and raises reached', () => {
    const jumped = jumpToChapter(progressAt(), 'ch-tour', BEATS);
    expect(jumped).toMatchObject({ cursor: REPORT, reached: REPORT });
  });

  it('jumping backwards keeps the furthest-reached beat', () => {
    const start = progressAt({ cursor: REPORT, reached: REPORT });
    expect(jumpToChapter(start, 'ch-one', BEATS)).toMatchObject({
      cursor: WELCOME,
      reached: REPORT,
    });
  });

  it('ignores an unknown chapter id', () => {
    const start = progressAt({ cursor: ALERT, reached: ALERT });
    expect(jumpToChapter(start, 'ch-removed-by-a-content-edit', BEATS)).toBe(start);
  });
});

describe('applyEvidence · completion', () => {
  it('records satisfied objectives by beat id', () => {
    const applied = applyEvidence(progressAt(), evidence({ alertRaised: true }), BEATS);
    expect(applied.completedBeatIds).toEqual(['alert']);
  });

  it('records objectives regardless of where the cursor is', () => {
    const applied = applyEvidence(
      progressAt(),
      evidence({ alertRaised: true, reportReady: true }),
      BEATS,
    );
    expect(applied.completedBeatIds).toEqual(['alert', 'report']);
  });

  it('is idempotent and preserves identity when nothing is new', () => {
    const once = applyEvidence(progressAt(), evidence({ alertRaised: true }), BEATS);
    expect(applyEvidence(once, evidence({ alertRaised: true }), BEATS)).toBe(once);
  });

  it('preserves identity when no evidence is present at all', () => {
    const start = progressAt({ cursor: ALERT, reached: ALERT });
    expect(applyEvidence(start, EMPTY_EVIDENCE, BEATS)).toBe(start);
  });

  it('never un-records a completion when evidence recedes', () => {
    const done = applyEvidence(progressAt(), evidence({ alertRaised: true }), BEATS);
    expect(applyEvidence(done, EMPTY_EVIDENCE, BEATS).completedBeatIds).toEqual(['alert']);
  });
});

describe('applyEvidence · auto-advance', () => {
  it('advances when the current beat opted in and its objective is newly satisfied', () => {
    const start = progressAt({ cursor: WATCH, reached: WATCH });
    const applied = applyEvidence(start, evidence({ telemetryFlowing: true }), BEATS);
    expect(applied).toMatchObject({ cursor: ALERT, reached: ALERT });
    expect(applied.completedBeatIds).toEqual(['watch']);
  });

  it('holds the operator on a beat that did not opt in', () => {
    const start = progressAt({ cursor: ALERT, reached: ALERT });
    const applied = applyEvidence(start, evidence({ alertRaised: true }), BEATS);
    expect(applied.cursor).toBe(ALERT);
    expect(applied.completedBeatIds).toEqual(['alert']);
  });

  it('does not advance a beat whose objective was already checked off before arrival', () => {
    // The operator raced ahead: telemetry was recorded while they were still on welcome.
    const early = applyEvidence(progressAt(), evidence({ telemetryFlowing: true }), BEATS);
    expect(early.cursor).toBe(WELCOME);

    const arrived = goNext(early, BEATS);
    expect(arrived.cursor).toBe(WATCH);
    // Arriving on the already-satisfied beat must not bounce them straight off it.
    expect(applyEvidence(arrived, evidence({ telemetryFlowing: true }), BEATS)).toBe(arrived);
  });

  it('does not skip past a beat the operator has not seen', () => {
    // Every objective in the fixture is satisfied at once while the cursor sits on `watch`.
    const start = progressAt({ cursor: WATCH, reached: WATCH });
    const applied = applyEvidence(
      start,
      evidence({
        telemetryFlowing: true,
        alertRaised: true,
        incidentOpened: true,
        reportReady: true,
      }),
      BEATS,
    );
    // One step only: the operator still has to read the alert beat.
    expect(applied.cursor).toBe(ALERT);
  });

  it('cannot advance through a learn beat', () => {
    const start = progressAt({ cursor: BRIEF, reached: BRIEF });
    const applied = applyEvidence(start, evidence({ incidentOpened: true }), BEATS);
    expect(applied.cursor).toBe(BRIEF);
  });

  it('stops at the final beat', () => {
    const start = progressAt({ cursor: OPEN, reached: OPEN });
    const applied = applyEvidence(start, evidence({ incidentOpened: true }), BEATS);
    expect(applied.cursor).toBe(REPORT);
    expect(applyEvidence(applied, evidence({ reportReady: true }), BEATS).cursor).toBe(REPORT);
  });
});

describe('clampProgress', () => {
  it('pulls an out-of-range cursor back into the walkthrough', () => {
    const stale = progressAt({ cursor: 99, reached: 99 });
    expect(clampProgress(stale, BEATS)).toMatchObject({ cursor: REPORT, reached: REPORT });
  });

  it('rejects negative and non-finite indices', () => {
    expect(clampProgress(progressAt({ cursor: -4, reached: -4 }), BEATS)).toMatchObject({
      cursor: 0,
      reached: 0,
    });
    expect(
      clampProgress(progressAt({ cursor: Number.NaN, reached: Number.NaN }), BEATS).cursor,
    ).toBe(0);
  });

  it('keeps reached at or ahead of the cursor', () => {
    expect(clampProgress(progressAt({ cursor: OPEN, reached: 0 }), BEATS).reached).toBe(OPEN);
  });

  it('preserves identity when already in range', () => {
    const clean = progressAt({ cursor: ALERT, reached: ALERT });
    expect(clampProgress(clean, BEATS)).toBe(clean);
  });
});

describe('resolveCurrentBeat', () => {
  it('resolves the cursor, clamping stale indices', () => {
    expect(resolveCurrentBeat(progressAt({ cursor: BRIEF }), BEATS)?.beat.id).toBe('brief');
    expect(resolveCurrentBeat(progressAt({ cursor: 99 }), BEATS)?.beat.id).toBe('report');
  });

  it('returns null when there is no content', () => {
    expect(resolveCurrentBeat(progressAt(), [])).toBeNull();
  });
});

describe('pendingObjectiveKeys', () => {
  it('is empty at the start — nothing reached has an outstanding objective', () => {
    expect(pendingObjectiveKeys(progressAt(), BEATS)).toEqual([]);
  });

  it('only reports objectives the operator has actually reached', () => {
    expect(pendingObjectiveKeys(progressAt({ cursor: WATCH, reached: WATCH }), BEATS)).toEqual([
      'telemetryFlowing',
    ]);
    expect(pendingObjectiveKeys(progressAt({ cursor: ALERT, reached: ALERT }), BEATS)).toEqual([
      'telemetryFlowing',
      'alertRaised',
    ]);
  });

  it('drops an objective once it is completed', () => {
    const progress = progressAt({ cursor: ALERT, reached: ALERT, completedBeatIds: ['watch'] });
    expect(pendingObjectiveKeys(progress, BEATS)).toEqual(['alertRaised']);
  });

  it('still reports an outstanding objective the operator stepped back past', () => {
    const progress = progressAt({ cursor: WELCOME, reached: REPORT, completedBeatIds: [] });
    expect(pendingObjectiveKeys(progress, BEATS)).toEqual([
      'telemetryFlowing',
      'alertRaised',
      'incidentOpened',
      'reportReady',
    ]);
  });
});

describe('isWalkthroughComplete', () => {
  it('is false while beats remain unseen', () => {
    expect(isWalkthroughComplete(progressAt({ cursor: OPEN, reached: OPEN }), BEATS)).toBe(false);
  });

  it('is false when a seen objective is still outstanding', () => {
    expect(isWalkthroughComplete(progressAt({ cursor: REPORT, reached: REPORT }), BEATS)).toBe(
      false,
    );
  });

  it('is true once every beat is seen and every objective is checked off', () => {
    const progress = progressAt({
      cursor: REPORT,
      reached: REPORT,
      completedBeatIds: ['watch', 'alert', 'open', 'report'],
    });
    expect(isWalkthroughComplete(progress, BEATS)).toBe(true);
  });
});

describe('flag setters', () => {
  it('toggle without disturbing anything else, preserving identity when unchanged', () => {
    const start = progressAt({ cursor: ALERT, reached: ALERT, completedBeatIds: ['watch'] });

    const minimized = setMinimized(start, true);
    expect(minimized).toMatchObject({
      minimized: true,
      cursor: ALERT,
      completedBeatIds: ['watch'],
    });
    expect(setMinimized(minimized, true)).toBe(minimized);

    const dismissed = setDismissed(start, true);
    // Dismissal is a reopenable door: the cursor and completions survive it.
    expect(dismissed).toMatchObject({
      dismissed: true,
      cursor: ALERT,
      reached: ALERT,
      completedBeatIds: ['watch'],
    });
    expect(setDismissed(dismissed, true)).toBe(dismissed);
    expect(setDismissed(dismissed, false).dismissed).toBe(false);
  });
});

describe('objectiveBlockReason', () => {
  it('is null for a learn beat', () => {
    expect(objectiveBlockReason(beatAt(WELCOME), progressAt(), EMPTY_EVIDENCE)).toBeNull();
  });

  it('blocks a required objective until its evidence lands', () => {
    const beat = beatAt(WATCH);
    expect(objectiveBlockReason(beat, progressAt(), EMPTY_EVIDENCE)).toBe('Wait for telemetry');
    expect(
      objectiveBlockReason(beat, progressAt(), evidence({ telemetryFlowing: true })),
    ).toBeNull();
  });

  it('treats a completed beat id as resolved even without live evidence', () => {
    const beat = beatAt(WATCH);
    const done = progressAt({ completedBeatIds: ['watch'] });
    expect(objectiveBlockReason(beat, done, EMPTY_EVIDENCE)).toBeNull();
  });

  it('blocks a skippable objective until it is satisfied or explicitly skipped', () => {
    const beat = beatAt(REPORT);
    expect(objectiveBlockReason(beat, progressAt(), EMPTY_EVIDENCE)).toBe('Wait for it');
    expect(objectiveBlockReason(beat, progressAt(), evidence({ reportReady: true }))).toBeNull();

    const skipped = skipObjective(progressAt(), 'report');
    expect(objectiveBlockReason(beat, skipped, EMPTY_EVIDENCE)).toBeNull();
  });
});

describe('skipObjective', () => {
  it('records the beat id and is idempotent, preserving identity when already skipped', () => {
    const skipped = skipObjective(progressAt(), 'report');
    expect(skipped.skippedBeatIds).toEqual(['report']);
    expect(skipObjective(skipped, 'report')).toBe(skipped);
  });

  it('never touches completedBeatIds', () => {
    const skipped = skipObjective(progressAt({ completedBeatIds: ['watch'] }), 'report');
    expect(skipped.completedBeatIds).toEqual(['watch']);
  });
});

describe('objectiveAudit', () => {
  it('reports every objective beat as met, skipped or unmet', () => {
    const progress = progressAt({
      cursor: REPORT,
      reached: REPORT,
      completedBeatIds: ['watch', 'alert'],
      skippedBeatIds: ['open'],
    });
    const audit = objectiveAudit(progress, BEATS, EMPTY_EVIDENCE);
    expect(audit.map((entry) => [entry.beatId, entry.status])).toEqual([
      ['watch', 'met'],
      ['alert', 'met'],
      ['open', 'skipped'],
      ['report', 'unmet'],
    ]);
  });

  it('reads live evidence as well as persisted completion', () => {
    const audit = objectiveAudit(progressAt(), BEATS, evidence({ alertRaised: true }));
    const alert = audit.find((entry) => entry.beatId === 'alert');
    expect(alert?.status).toBe('met');
  });

  it('carries the declared requirement through', () => {
    const audit = objectiveAudit(progressAt(), BEATS, EMPTY_EVIDENCE);
    expect(audit.find((entry) => entry.beatId === 'report')?.requirement).toBe('skippable');
    expect(audit.find((entry) => entry.beatId === 'watch')?.requirement).toBe('required');
  });

  it('excludes learn beats, which have no objective', () => {
    const audit = objectiveAudit(progressAt(), BEATS, EMPTY_EVIDENCE);
    expect(audit.some((entry) => entry.beatId === 'welcome')).toBe(false);
  });
});

describe('empty content', () => {
  it('leaves progress untouched rather than producing an out-of-range cursor', () => {
    const start = progressAt();
    expect(goNext(start, [])).toBe(start);
    expect(skipChapter(start, [])).toBe(start);
    expect(jumpToChapter(start, 'ch-one', [])).toBe(start);
    expect(applyEvidence(start, evidence({ alertRaised: true }), [])).toBe(start);
    expect(pendingObjectiveKeys(start, [])).toEqual([]);
    expect(isWalkthroughComplete(start, [])).toBe(true);
  });
});

describe('stored progress contract', () => {
  it('starts at the version the storage layer gates on', () => {
    expect(INITIAL_PROGRESS.version).toBe(TUTORIAL_PROGRESS_VERSION);
    expect(INITIAL_PROGRESS).toMatchObject({ cursor: 0, reached: 0, dismissed: false });
  });
});
