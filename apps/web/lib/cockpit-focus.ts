/**
 * Where a keyboard operator lands when the control they came from no longer exists.
 *
 * Summoning a context sheet can fold the surface its invoker lived on — clicking an alert
 * card's asset button opens the inspector sheet, and the collision rule collapses the
 * signals stack that held the button in the same commit. The sheet's normal focus restore
 * has nothing connected to return to, so focus falls to `<body>` and the operator's place
 * in the room is gone.
 *
 * These are the cockpit's surviving anchors, nearest first: the signals capsule (the
 * collapsed stack's own representative, so re-opening the stack is one key away), then the
 * console band (the cockpit's single Tab stop). Both are addressed by test id because they
 * are chrome landmarks — the same identity the tutorial and the e2e suite anchor on.
 */

export const SIGNALS_CAPSULE_TESTID = 'signals-capsule';
export const COCKPIT_CONSOLE_TESTID = 'cockpit-console';

const FALLBACK_SELECTORS = [
  `[data-testid="${SIGNALS_CAPSULE_TESTID}"]`,
  `[data-testid="${COCKPIT_CONSOLE_TESTID}"] [tabindex="0"]`,
];

/** The nearest surviving cockpit anchor to hand focus back to, or `null` if none is mounted. */
export function resolveCockpitFallbackFocus(): HTMLElement | null {
  if (typeof document === 'undefined') {
    return null;
  }
  for (const selector of FALLBACK_SELECTORS) {
    const candidate = document.querySelector<HTMLElement>(selector);
    if (candidate?.isConnected) {
      return candidate;
    }
  }
  return null;
}
