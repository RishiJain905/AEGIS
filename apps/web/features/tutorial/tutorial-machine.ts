/**
 * Pure state machine for the guided walkthrough.
 *
 * The walkthrough is chapters of beats (see `tutorial-contract`). This module owns the
 * rules for where the operator is, how they move, and when live run evidence checks an
 * objective off. It is deliberately free of React and browser APIs so every rule below is
 * directly unit-testable.
 *
 * Three invariants shape everything here:
 *
 *  - **`goNext` is an unconditional mover.** It never reads objectives and never refuses to
 *    advance — the machine's pure movement primitive has no opinion on gating. Whether the
 *    operator is *allowed* to call it right now is a separate question, answered by
 *    {@link objectiveBlockReason} and enforced by the caller (the overlay disables `Next` and
 *    intercepts its own keyboard shortcuts). This split keeps "where the cursor goes" and
 *    "should it be allowed to go there yet" independently testable.
 *  - **Monotonic `reached`.** `cursor` is where the operator is; `reached` is the furthest
 *    beat ever visited. Back moves the cursor and never lowers `reached`, so stepping back to
 *    re-read a beat can't cost progress, and a reload resumes rather than restarts.
 *  - **Completion is keyed by beat id.** Editing, reordering or inserting content changes
 *    indices; ids are stable, so stored progress survives content edits — and the same is
 *    true of `skippedBeatIds`, which records an explicit "Skip objective" the same way.
 *
 * Every mutator returns the *same object identity* when nothing changed, so callers can skip
 * redundant localStorage writes and re-renders.
 */

import type {
  ResolvedBeat,
  TutorialBeat,
  TutorialChapter,
  TutorialEvidence,
  TutorialEvidenceKey,
  TutorialObjectiveRequirement,
  TutorialProgress,
} from './tutorial-contract';

/**
 * Expand chapters into the flat, positioned beat list the overlay renders from. The result
 * is the machine's index space: every cursor in `TutorialProgress` indexes into it.
 */
export function flattenChapters(chapters: readonly TutorialChapter[]): ResolvedBeat[] {
  const chapterCount = chapters.length;
  const resolved: ResolvedBeat[] = [];
  let index = 0;

  chapters.forEach((chapter, chapterIndex) => {
    const beatCount = chapter.beats.length;
    chapter.beats.forEach((beat, beatIndex) => {
      resolved.push({
        beat,
        chapter,
        index,
        beatNumber: beatIndex + 1,
        beatCount,
        chapterNumber: chapterIndex + 1,
        chapterCount,
      });
      index += 1;
    });
  });

  return resolved;
}

/**
 * Whether a beat's objective is met by the current evidence.
 *
 * A beat with no objective (`learn`) has nothing to satisfy and answers `false` — there is no
 * objective, so no objective is satisfied. Callers only read this for `do` beats; keeping it
 * false is what stops auto-advance from ever running through a `learn` beat.
 */
export function isObjectiveSatisfied(beat: TutorialBeat, evidence: TutorialEvidence): boolean {
  const key = beat.objective?.evidence;
  if (!key) {
    return false;
  }
  return evidence[key];
}

function clampIndex(value: number, beats: readonly ResolvedBeat[]): number {
  if (beats.length === 0) {
    return 0;
  }
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(Math.trunc(value), beats.length - 1));
}

/**
 * Force a progress record into range for the given beat list, keeping `reached` at or ahead
 * of `cursor`. Content can shrink between sessions, so stored indices are never trusted.
 */
export function clampProgress(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  const cursor = clampIndex(progress.cursor, beats);
  const reached = Math.max(cursor, clampIndex(progress.reached, beats));
  if (cursor === progress.cursor && reached === progress.reached) {
    return progress;
  }
  return { ...progress, cursor, reached };
}

/** Move the cursor, raising `reached` monotonically. Identity-preserving when static. */
function withCursor(
  progress: TutorialProgress,
  nextCursor: number,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  const cursor = clampIndex(nextCursor, beats);
  const reached = Math.max(cursor, clampIndex(progress.reached, beats));
  if (cursor === progress.cursor && reached === progress.reached) {
    return progress;
  }
  return { ...progress, cursor, reached };
}

/** The beat the operator is currently on, or `null` when there is no content. */
export function resolveCurrentBeat(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): ResolvedBeat | null {
  if (beats.length === 0) {
    return null;
  }
  return beats[clampIndex(progress.cursor, beats)] ?? null;
}

/**
 * Fold a fresh evidence snapshot into progress.
 *
 * Two separate effects:
 *  1. Every satisfied objective is recorded in `completedBeatIds`. Recording is independent of
 *     where the cursor is — an objective is a fact about the run, not about the operator's
 *     position — and is idempotent.
 *  2. The current beat auto-advances iff its objective is *newly* satisfied by this snapshot
 *     and the beat opted in with `advanceOnSatisfied`. "Newly" matters: arriving on a beat
 *     whose objective was checked off earlier must not bounce the operator straight past the
 *     copy explaining what they did. Exactly one step per snapshot, and a `learn` beat can
 *     never satisfy its objective, so an auto-advance run always stops at the next thing the
 *     operator has to read.
 */
export function applyEvidence(
  progress: TutorialProgress,
  evidence: TutorialEvidence,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  if (beats.length === 0) {
    return progress;
  }

  const completed = new Set(progress.completedBeatIds);
  const newlyCompleted: string[] = [];
  for (const resolved of beats) {
    const { id } = resolved.beat;
    if (completed.has(id)) {
      continue;
    }
    if (isObjectiveSatisfied(resolved.beat, evidence)) {
      completed.add(id);
      newlyCompleted.push(id);
    }
  }

  if (newlyCompleted.length === 0) {
    return clampProgress(progress, beats);
  }

  const current = beats[clampIndex(progress.cursor, beats)];
  const advance =
    current !== undefined &&
    current.beat.objective?.advanceOnSatisfied === true &&
    newlyCompleted.includes(current.beat.id);

  const withCompletions: TutorialProgress = {
    ...progress,
    completedBeatIds: [...progress.completedBeatIds, ...newlyCompleted],
  };

  const cursor = advance ? clampIndex(progress.cursor, beats) + 1 : withCompletions.cursor;
  return withCursor(withCompletions, cursor, beats);
}

/**
 * Advance one beat. This mover has no opinion on gating — see the module doc — so the beat
 * the operator leaves keeps its objective live and can still self-complete later. Callers that
 * must respect a beat's declared requirement check {@link objectiveBlockReason} first.
 */
export function goNext(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  return withCursor(progress, clampIndex(progress.cursor, beats) + 1, beats);
}

/**
 * Whether a beat's objective is resolved: satisfied by evidence (persisted or live) or, for a
 * `skippable` objective, explicitly skipped. Shared by the gate check and the audit below so
 * the two can never disagree about what counts as "done with this beat".
 */
function isObjectiveResolved(
  beat: TutorialBeat,
  progress: TutorialProgress,
  evidence: TutorialEvidence,
): boolean {
  if (progress.completedBeatIds.includes(beat.id) || isObjectiveSatisfied(beat, evidence)) {
    return true;
  }
  return progress.skippedBeatIds.includes(beat.id);
}

/**
 * Why `Next` should be refused for this beat right now, or `null` if it should not be.
 *
 * `learn` beats and `optional` objectives never block. A `required` or `skippable` objective
 * blocks until it is resolved (see {@link isObjectiveResolved}) — the difference between the
 * two is only in *how* it can be resolved: a `required` objective only by its evidence
 * landing, a `skippable` one also by an explicit skip. The returned string is the objective's
 * own `pending` copy, so the caller has a ready-made reason to display.
 */
export function objectiveBlockReason(
  beat: TutorialBeat,
  progress: TutorialProgress,
  evidence: TutorialEvidence,
): string | null {
  const objective = beat.objective;
  if (!objective || objective.requirement === 'optional') {
    return null;
  }
  if (isObjectiveResolved(beat, progress, evidence)) {
    return null;
  }
  return objective.pending;
}

/**
 * Record that the operator explicitly skipped a beat's `skippable` objective. Idempotent —
 * skipping twice is a no-op that preserves identity, same as every other mutator here.
 *
 * Skipping never touches `completedBeatIds`: a skipped objective was never met, and the two
 * lists staying disjoint in practice is exactly what lets the audit below tell the two apart.
 */
export function skipObjective(progress: TutorialProgress, beatId: string): TutorialProgress {
  if (progress.skippedBeatIds.includes(beatId)) {
    return progress;
  }
  return { ...progress, skippedBeatIds: [...progress.skippedBeatIds, beatId] };
}

/**
 * Step back one beat. `reached` is untouched, so going back to re-read something never costs
 * the operator the ability to return to where they were.
 */
export function goBack(progress: TutorialProgress): TutorialProgress {
  const cursor = Math.max(0, Math.trunc(progress.cursor) - 1);
  if (cursor === progress.cursor) {
    return progress;
  }
  return { ...progress, cursor };
}

/**
 * Jump to the first beat of the next chapter. On the final chapter this lands on its last
 * beat rather than dropping out of the walkthrough — leaving is `onDismiss`, not this.
 */
export function skipChapter(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  const current = beats[clampIndex(progress.cursor, beats)];
  if (!current) {
    return progress;
  }
  const target = beats.find(
    (candidate) => candidate.index > current.index && candidate.chapter.id !== current.chapter.id,
  );
  return withCursor(progress, target ? target.index : beats.length - 1, beats);
}

/**
 * Jump to the first beat of a named chapter. An unknown id is a no-op — the chapter menu is
 * rendered from the same content, but stored/deep-linked ids can outlive a content edit.
 */
export function jumpToChapter(
  progress: TutorialProgress,
  chapterId: string,
  beats: readonly ResolvedBeat[],
): TutorialProgress {
  const target = beats.find((candidate) => candidate.chapter.id === chapterId);
  if (!target) {
    return progress;
  }
  return withCursor(progress, target.index, beats);
}

/** Set the minimized flag, preserving identity when it already holds. */
export function setMinimized(progress: TutorialProgress, minimized: boolean): TutorialProgress {
  if (progress.minimized === minimized) {
    return progress;
  }
  return { ...progress, minimized };
}

/** Set the dismissed flag. Dismissal never clears progress — it is a reopenable door. */
export function setDismissed(progress: TutorialProgress, dismissed: boolean): TutorialProgress {
  if (progress.dismissed === dismissed) {
    return progress;
  }
  return { ...progress, dismissed };
}

/**
 * The evidence keys still worth observing: objectives on beats the operator has actually
 * reached that are not yet checked off.
 *
 * This is the polling budget. The React layer only runs the queries backing these keys, so a
 * walkthrough sitting on chapter one costs one query rather than five, and a finished
 * walkthrough costs none. Objectives beyond `reached` are excluded deliberately — evidence
 * that lands before the operator gets there is picked up the moment they arrive.
 */
export function pendingObjectiveKeys(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): TutorialEvidenceKey[] {
  if (beats.length === 0) {
    return [];
  }
  const completed = new Set(progress.completedBeatIds);
  const reached = Math.max(clampIndex(progress.cursor, beats), clampIndex(progress.reached, beats));
  const keys = new Set<TutorialEvidenceKey>();
  for (const resolved of beats) {
    if (resolved.index > reached) {
      break;
    }
    const key = resolved.beat.objective?.evidence;
    if (key && !completed.has(resolved.beat.id)) {
      keys.add(key);
    }
  }
  return [...keys];
}

/**
 * Whether the walkthrough has run its course: the operator has seen the last beat and no
 * objective they passed is still outstanding. Used to stand the evidence polling down.
 */
export function isWalkthroughComplete(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
): boolean {
  if (beats.length === 0) {
    return true;
  }
  if (clampIndex(progress.reached, beats) < beats.length - 1) {
    return false;
  }
  return pendingObjectiveKeys(progress, beats).length === 0;
}

/** One objective's final disposition, as reported by {@link objectiveAudit}. */
export interface ObjectiveAuditEntry {
  beatId: string;
  beatTitle: string;
  chapterId: string;
  chapterTitle: string;
  /** Absolute index of the beat, for filtering against `reached`. */
  index: number;
  requirement: TutorialObjectiveRequirement;
  status: 'met' | 'skipped' | 'unmet';
}

/**
 * Every `do` beat's objective, in walkthrough order, with how it was actually resolved.
 *
 * This is the honest accounting BUG-006 asks for: a `required` or `skippable` objective that
 * was never satisfied and never explicitly skipped — which can only happen by jumping or
 * skipping past its *chapter*, since `Next` itself refuses to — still shows up here as
 * `unmet` rather than silently reading as complete. Feeds the completion summary and the
 * chapter menu's unresolved marker from one shared source of truth.
 */
export function objectiveAudit(
  progress: TutorialProgress,
  beats: readonly ResolvedBeat[],
  evidence: TutorialEvidence,
): ObjectiveAuditEntry[] {
  const entries: ObjectiveAuditEntry[] = [];
  for (const resolved of beats) {
    const { beat, chapter } = resolved;
    const objective = beat.objective;
    if (!objective) {
      continue;
    }
    const met = progress.completedBeatIds.includes(beat.id) || isObjectiveSatisfied(beat, evidence);
    const skipped = !met && progress.skippedBeatIds.includes(beat.id);
    entries.push({
      beatId: beat.id,
      beatTitle: beat.title,
      chapterId: chapter.id,
      chapterTitle: chapter.title,
      index: resolved.index,
      requirement: objective.requirement,
      status: met ? 'met' : skipped ? 'skipped' : 'unmet',
    });
  }
  return entries;
}
