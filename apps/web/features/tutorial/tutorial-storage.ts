import { INITIAL_PROGRESS, type TutorialProgress } from './tutorial-machine';

/**
 * localStorage persistence for the guided walkthrough.
 *
 * Progress is keyed by runId so reloading a run resumes where the operator left off, and
 * an "active" pointer records which run's tutorial is in flight so the overlay stays
 * armed while the operator navigates to shell pages that do not carry the runId in the
 * URL (e.g. an incident route). All access is guarded for SSR and quota/serialization
 * failures so the overlay can never take the app down.
 */

const PROGRESS_PREFIX = 'aegis:tutorial:progress:';
const ACTIVE_POINTER_KEY = 'aegis:tutorial:active';

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

export function loadProgress(runId: string): TutorialProgress {
  const storage = safeStorage();
  if (!storage || !runId) {
    return { ...INITIAL_PROGRESS };
  }
  try {
    const raw = storage.getItem(progressKey(runId));
    if (!raw) {
      return { ...INITIAL_PROGRESS };
    }
    const parsed = JSON.parse(raw) as Partial<TutorialProgress>;
    return {
      reached:
        typeof parsed.reached === 'number' && Number.isFinite(parsed.reached)
          ? Math.max(0, Math.trunc(parsed.reached))
          : 0,
      welcomeAcknowledged: parsed.welcomeAcknowledged === true,
      dismissed: parsed.dismissed === true,
    };
  } catch {
    return { ...INITIAL_PROGRESS };
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
 * Arm the guided walkthrough for a run the operator just launched. Sets the active
 * pointer and seeds fresh progress so the overlay appears immediately on the run page.
 */
export function armTutorial(runId: string): void {
  if (!runId) {
    return;
  }
  setActiveTutorialRunId(runId);
  saveProgress(runId, { ...INITIAL_PROGRESS });
}
