export interface ReconnectBackoffOptions {
  minDelayMs?: number;
  maxDelayMs?: number;
  multiplier?: number;
  jitterRatio?: number;
}

export function computeReconnectDelayMs(
  attempt: number,
  options: ReconnectBackoffOptions = {},
): number {
  const minDelayMs = options.minDelayMs ?? 250;
  const maxDelayMs = options.maxDelayMs ?? 30_000;
  const multiplier = options.multiplier ?? 2;
  const jitterRatio = options.jitterRatio ?? 0.2;

  const base = Math.min(maxDelayMs, minDelayMs * multiplier ** Math.max(0, attempt - 1));
  const jitter = base * jitterRatio * (Math.random() * 2 - 1);
  return Math.max(minDelayMs, Math.round(base + jitter));
}
