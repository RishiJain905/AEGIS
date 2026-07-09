import type { ReturnToLiveResultV1 } from '@aegis/contracts-ts';

export function buildReturnToLiveResult(
  runId: string,
  fromSequence: number,
  completedAt: string = new Date().toISOString(),
): ReturnToLiveResultV1 {
  return {
    schemaVersion: 1,
    runId,
    fromSequence,
    liveRoute: `/runs/${runId}`,
    authoritativeResyncRequired: true,
    replayStoreCleared: true,
    completedAt,
  };
}
