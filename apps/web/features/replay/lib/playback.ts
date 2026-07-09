import type { ReplayPlaybackSpeed } from '@aegis/contracts-ts';

export const REPLAY_SPEEDS: ReplayPlaybackSpeed[] = ['0.5x', '1x', '2x', '4x'];

export function speedToIntervalMs(speed: ReplayPlaybackSpeed, reducedMotion: boolean): number {
  if (reducedMotion) {
    return Number.POSITIVE_INFINITY;
  }
  switch (speed) {
    case '0.5x':
      return 1600;
    case '1x':
      return 800;
    case '2x':
      return 400;
    case '4x':
      return 200;
    default: {
      const _exhaustive: never = speed;
      return _exhaustive;
    }
  }
}

export function nextSpeed(speed: ReplayPlaybackSpeed): ReplayPlaybackSpeed {
  const index = REPLAY_SPEEDS.indexOf(speed);
  return REPLAY_SPEEDS[Math.min(REPLAY_SPEEDS.length - 1, index + 1)] ?? '1x';
}

export function previousSpeed(speed: ReplayPlaybackSpeed): ReplayPlaybackSpeed {
  const index = REPLAY_SPEEDS.indexOf(speed);
  return REPLAY_SPEEDS[Math.max(0, index - 1)] ?? '1x';
}

export function clampSequence(sequence: number, minSequence: number, maxSequence: number): number {
  return Math.max(minSequence, Math.min(maxSequence, sequence));
}
