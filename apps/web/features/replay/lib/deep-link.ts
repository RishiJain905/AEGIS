/**
 * Parse the `?sequence=` deep-link query parameter used by after-action and
 * scoring "jump to replay seq N" links. Returns a non-negative integer, or
 * `undefined` when the value is missing or malformed (in which case the replay
 * opens at its default cursor).
 */
export function parseReplaySequenceParam(raw: string | string[] | undefined): number | undefined {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (value == null || value === '') {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return undefined;
  }
  return parsed;
}
