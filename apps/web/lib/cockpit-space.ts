/**
 * The cockpit's space budget, expressed once so the furniture agrees with itself.
 *
 * The design contract fixes how much of the stage each sheet may claim: alone the inspector
 * takes at most `min(30rem, 42%)` and the copilot `min(28rem, 40%)`; sharing, both clamp to
 * `min(26rem, 32%)` so at least 36% of the stage stays un-occluded at every supported width.
 *
 * The signals capsule docks against the open sheet's leading edge, which means it has to
 * know the same numbers — when they were written twice, the capsule floated over the sheet
 * header and covered the subject line as soon as the sheet narrowed. These are plain CSS
 * length expressions rather than Tailwind classes precisely because both a `width` and a
 * `right` offset are computed from them.
 */

/** Width of a sheet holding its side alone. */
export const INSPECTOR_SHEET_WIDTH_SOLO = 'min(30rem, 42%)';
export const COPILOT_SHEET_WIDTH_SOLO = 'min(28rem, 40%)';

/** Width of either sheet when both sides are claimed. */
export const SHEET_WIDTH_SHARED = 'min(26rem, 32%)';

/** Gap between the inspector sheet's leading edge and the docked signals capsule. */
const CAPSULE_DOCK_GAP = '0.75rem';

/**
 * The graph's own floating chrome row — search on the left, View options and the zoom
 * cluster on the right — which claims the same top edge of the stage that the signals
 * furniture floats over.
 *
 * The two collided: signals sat at a fixed 6rem from the stage's top, but the band above it
 * is not a fixed height. The stage header wraps, the chrome row itself wraps at narrower
 * widths, and either pushes the zoom cluster down into signals' 6rem — so the capsule
 * rendered on top of the +/−/Reset buttons and swallowed the clicks. No constant clears a
 * band whose height depends on width and state, so signals measures this row instead.
 */
export const GRAPH_CHROME_ROW_TESTID = 'graph-chrome-row';
export const COCKPIT_STAGE_TESTID = 'cockpit-stage';

/** Breathing room between the graph's chrome row and the signals furniture below it. */
const SIGNALS_CHROME_GAP_PX = 12;

/**
 * How far below the stage's top the signals furniture may start: clear of the graph's chrome
 * row wherever that row currently ends. Falls back to the historical 6rem when there is no
 * chrome row to measure — the replay and stacked layouts, and tests.
 */
export const SIGNALS_DEFAULT_TOP_PX = 96;

export function resolveSignalsTopOffset(): number {
  if (typeof document === 'undefined') {
    return SIGNALS_DEFAULT_TOP_PX;
  }
  const stage = document.querySelector<HTMLElement>(`[data-testid="${COCKPIT_STAGE_TESTID}"]`);
  const chrome = document.querySelector<HTMLElement>(`[data-testid="${GRAPH_CHROME_ROW_TESTID}"]`);
  if (!stage || !chrome) {
    return SIGNALS_DEFAULT_TOP_PX;
  }
  const clearance =
    chrome.getBoundingClientRect().bottom -
    stage.getBoundingClientRect().top +
    SIGNALS_CHROME_GAP_PX;
  // Never above the historical resting place: a zero-height measurement (an unlaid-out
  // canvas, jsdom) must not float signals up into the chrome it is trying to clear.
  return Math.max(SIGNALS_DEFAULT_TOP_PX, Math.round(clearance));
}

export function inspectorSheetWidth(shared: boolean): string {
  return shared ? SHEET_WIDTH_SHARED : INSPECTOR_SHEET_WIDTH_SOLO;
}

export function copilotSheetWidth(shared: boolean): string {
  return shared ? SHEET_WIDTH_SHARED : COPILOT_SHEET_WIDTH_SOLO;
}

/**
 * How far in from the stage's right edge the signals capsule sits: clear of the inspector
 * sheet when one is open, a normal inset otherwise.
 */
export function signalsCapsuleRightOffset(inspectorOpen: boolean, copilotOpen: boolean): string {
  if (!inspectorOpen) {
    return '0.75rem';
  }
  return `calc(${inspectorSheetWidth(copilotOpen)} + ${CAPSULE_DOCK_GAP})`;
}
