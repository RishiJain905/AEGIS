/**
 * localStorage persistence for the guided walkthrough.
 *
 * Progress is keyed by run id so reloading a run resumes where the operator left off, and an
 * "active" pointer records which run's tutorial is in flight so the overlay stays armed while
 * the operator navigates to shell pages that do not carry the run id in the URL (an incident
 * route, the reports workspace, admin).
 *
 * Every access is guarded for SSR and for quota/serialisation failures: the walkthrough is
 * decoration on top of the cockpit, so a storage fault degrades it to "starts from the top"
 * and can never take the app down.
 *
 * Stored progress is version-tagged, and an older record is only ever read when the upgrade to
 * the current shape is provably lossless. v1 was not: it had no cursor and a differently-shaped
 * completion model, and reading it as if it were the current shape is how you get a walkthrough
 * that opens mid-way through a chapter the operator has never seen — so v1 is discarded. v2 and
 * v3 are, because v3 only added `clockHeld` and v4 only adds `skippedBeatIds`, and the correct
 * value of a field for a record written before it existed is exactly its default (`false` and
 * `[]` respectively). Discarding v2/v3 would restart the walkthrough of every operator mid-run,
 * which is a worse outcome than the one the version tag exists to prevent.
 */

import {
  INITIAL_PROGRESS,
  TUTORIAL_PROGRESS_VERSION,
  type TutorialProgress,
} from './tutorial-contract';

const PROGRESS_PREFIX = 'aegis:tutorial:progress:';
const ACTIVE_POINTER_KEY = 'aegis:tutorial:active';
const ARM_TOKEN_KEY = 'aegis:tutorial:arm-token';

/**
 * Fired on `window` whenever the walkthrough is armed or resumed.
 *
 * The `storage` event only reaches *other* tabs, so a same-tab re-arm is invisible without
 * this. The overlay lives at the shell layout and stays mounted across SPA navigation, which
 * is exactly the case that needs it: restarting the training run reuses the same run id (it
 * derives from seed + scenario version), so nothing in the route or the pointer changes and
 * the controller would otherwise keep rendering the pre-restart cursor.
 */
export const TUTORIAL_ARMED_EVENT = 'aegis:tutorial:armed';

/**
 * In-memory mirror of the arm token, so re-arming still re-initialises the overlay when
 * localStorage is unavailable (privacy modes) and every read would otherwise return the same
 * value forever. Module state is shared by every importer in the page.
 */
let armTokenFallback = 0;

function safeStorage(): Storage | null {
  try {
    if (typeof window === 'undefined') {
      return null;
    }
    // Accessing localStorage can throw (e.g. privacy modes) — the try/catch guards it.
    return window.localStorage;
  } catch {
    return null;
  }
}

function progressKey(runId: string): string {
  return `${PROGRESS_PREFIX}${runId}`;
}

function freshProgress(): TutorialProgress {
  return { ...INITIAL_PROGRESS, completedBeatIds: [], skippedBeatIds: [] };
}

function nonNegativeInt(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0;
}

function beatIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  for (const entry of value) {
    if (typeof entry === 'string' && entry.length > 0) {
      seen.add(entry);
    }
  }
  return [...seen];
}

/**
 * Schema versions this reader accepts. v4 is current; v2 and v3 differ only by the absence of
 * `clockHeld` and `skippedBeatIds`, which default below to exactly the values they would have
 * had.
 */
const READABLE_PROGRESS_VERSIONS: ReadonlySet<number> = new Set([2, 3, TUTORIAL_PROGRESS_VERSION]);

/**
 * Read progress for a run. Returns a fresh record for an unknown run, unreadable storage,
 * malformed JSON, or a record written by a schema version that cannot be upgraded losslessly.
 *
 * Indices are only sanity-checked here (finite, non-negative); the machine clamps them
 * against the actual beat list, which is the only thing that knows how long it is.
 */
export function loadProgress(runId: string): TutorialProgress {
  const storage = safeStorage();
  if (!storage || !runId) {
    return freshProgress();
  }
  try {
    const raw = storage.getItem(progressKey(runId));
    if (!raw) {
      return freshProgress();
    }
    const parsed = JSON.parse(raw) as Partial<TutorialProgress> | null;
    if (!parsed || typeof parsed.version !== 'number') {
      return freshProgress();
    }
    if (!READABLE_PROGRESS_VERSIONS.has(parsed.version)) {
      return freshProgress();
    }
    const cursor = nonNegativeInt(parsed.cursor);
    return {
      version: TUTORIAL_PROGRESS_VERSION,
      cursor,
      reached: Math.max(cursor, nonNegativeInt(parsed.reached)),
      completedBeatIds: beatIds(parsed.completedBeatIds),
      // Absent on a v2/v3 record, which is indistinguishable from "nothing skipped yet".
      skippedBeatIds: beatIds(parsed.skippedBeatIds),
      minimized: parsed.minimized === true,
      dismissed: parsed.dismissed === true,
      // Absent on a v2 record, which is indistinguishable from "has not been held".
      clockHeld: parsed.clockHeld === true,
    };
  } catch {
    return freshProgress();
  }
}

export function saveProgress(runId: string, progress: TutorialProgress): void {
  const storage = safeStorage();
  if (!storage || !runId) {
    return;
  }
  try {
    storage.setItem(progressKey(runId), JSON.stringify(progress));
  } catch {
    // Ignore quota / serialization failures — progress persistence is best-effort.
  }
}

export function clearProgress(runId: string): void {
  const storage = safeStorage();
  if (!storage || !runId) {
    return;
  }
  try {
    storage.removeItem(progressKey(runId));
  } catch {
    // Ignore.
  }
}

export function getActiveTutorialRunId(): string | null {
  const storage = safeStorage();
  if (!storage) {
    return null;
  }
  try {
    return storage.getItem(ACTIVE_POINTER_KEY);
  } catch {
    return null;
  }
}

export function setActiveTutorialRunId(runId: string): void {
  const storage = safeStorage();
  if (!storage || !runId) {
    return;
  }
  try {
    storage.setItem(ACTIVE_POINTER_KEY, runId);
  } catch {
    // Ignore.
  }
}

export function clearActiveTutorialRunId(): void {
  const storage = safeStorage();
  if (!storage) {
    return;
  }
  try {
    storage.removeItem(ACTIVE_POINTER_KEY);
  } catch {
    // Ignore.
  }
}

/**
 * Monotonic count of how many times the walkthrough has been armed or resumed.
 *
 * Paired with the run id it forms the identity of "which walkthrough is on screen". The run
 * id alone is not enough: restarting the training run rebuilds the run under the *same* id,
 * so the token is the only thing that changes.
 */
export function getArmToken(): number {
  const storage = safeStorage();
  if (!storage) {
    return armTokenFallback;
  }
  try {
    const raw = storage.getItem(ARM_TOKEN_KEY);
    const parsed = raw == null ? Number.NaN : Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? Math.max(parsed, armTokenFallback) : armTokenFallback;
  } catch {
    return armTokenFallback;
  }
}

/** Bump the token and tell any mounted overlay to re-read what it is showing. */
function announceArm(): void {
  const next = getArmToken() + 1;
  armTokenFallback = next;
  const storage = safeStorage();
  if (storage) {
    try {
      storage.setItem(ARM_TOKEN_KEY, String(next));
    } catch {
      // Ignore — the in-memory mirror still carries this page session.
    }
  }
  if (typeof window !== 'undefined') {
    // Dispatched last, so a listener that re-reads storage sees the finished write.
    window.dispatchEvent(new Event(TUTORIAL_ARMED_EVENT));
  }
}

/**
 * Arm the guided walkthrough for a run the operator just launched. Sets the active pointer,
 * seeds fresh progress so the overlay opens at the first beat, and bumps the arm token so a
 * mounted overlay drops whatever it was showing and re-reads.
 */
export function armTutorial(runId: string): void {
  if (!runId) {
    return;
  }
  setActiveTutorialRunId(runId);
  saveProgress(runId, freshProgress());
  announceArm();
}

/**
 * Reopen a walkthrough the operator dismissed, without restarting it. Clears the dismissed
 * and minimized flags and re-arms the pointer; the cursor and every completed objective
 * survive. This is what makes dismissal a door rather than a cliff — `armTutorial` is the
 * deliberate restart.
 */
export function resumeTutorial(runId: string): void {
  if (!runId) {
    return;
  }
  const progress = loadProgress(runId);
  setActiveTutorialRunId(runId);
  saveProgress(runId, { ...progress, dismissed: false, minimized: false });
  // Same reason as arming: a mounted overlay is holding `dismissed: true` in memory and will
  // never re-read on its own, because the run id has not moved.
  announceArm();
}
