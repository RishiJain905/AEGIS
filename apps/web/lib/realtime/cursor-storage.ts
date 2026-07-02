const CURSOR_STORAGE_KEY = 'aegis.live-run.cursor';

export interface StoredRunCursor {
  runId: string;
  lastAppliedSequence: number;
  updatedAt: string;
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof sessionStorage !== 'undefined';
}

export function loadStoredCursor(runId: string): number {
  if (!isBrowser()) {
    return 0;
  }
  try {
    const raw = sessionStorage.getItem(CURSOR_STORAGE_KEY);
    if (raw === null) {
      return 0;
    }
    const parsed = JSON.parse(raw) as StoredRunCursor;
    if (parsed.runId !== runId) {
      return 0;
    }
    return parsed.lastAppliedSequence;
  } catch {
    return 0;
  }
}

export function saveStoredCursor(runId: string, lastAppliedSequence: number): void {
  if (!isBrowser()) {
    return;
  }
  const payload: StoredRunCursor = {
    runId,
    lastAppliedSequence,
    updatedAt: new Date().toISOString(),
  };
  sessionStorage.setItem(CURSOR_STORAGE_KEY, JSON.stringify(payload));
}

export function clearStoredCursor(): void {
  if (!isBrowser()) {
    return;
  }
  sessionStorage.removeItem(CURSOR_STORAGE_KEY);
}
