/**
 * The cockpit's single-key vocabulary, in one place.
 *
 * The console is the cockpit's keyboard position — one Tab stop for the whole band — and it
 * also routes printable keystrokes into the copilot composer. Those two facts collided: the
 * band swallowed every letter, so `A` (signals), `I` (inspector), `C` (copilot) and `T`
 * (chronicle) were unreachable from the only place a keyboard operator stands.
 *
 * The rule that resolves it: **a bound single-key shortcut always wins.** Only printable
 * input that is *not* a shortcut seeds the composer. Both sides read this list, so a key can
 * never be a shortcut on one surface and a character on another.
 */
export const COCKPIT_SHORTCUT_KEYS: ReadonlySet<string> = new Set(['a', 'i', 'c', 't']);

/**
 * True when a key press is claimed by the cockpit's shortcut vocabulary. Case-insensitive:
 * the shortcut handlers lower-case what they read, so `Shift+A` is the same shortcut and
 * must not seed an uppercase character instead.
 */
export function isCockpitShortcutKey(key: string): boolean {
  return key.length === 1 && COCKPIT_SHORTCUT_KEYS.has(key.toLowerCase());
}
