export type RelayoutTrigger = 'none' | 'incremental' | 'full';

export interface RelayoutTriggerInput {
  previousVisibleNodeIds: string[];
  nextVisibleNodeIds: string[];
  previousRevisionKey: string | null;
  nextRevisionKey: string;
  isInitialLoad: boolean;
}

const INCREMENTAL_NODE_DELTA_THRESHOLD = 5;
const FULL_NODE_DELTA_THRESHOLD = 100;

export function determineRelayoutTrigger(input: RelayoutTriggerInput): RelayoutTrigger {
  if (input.isInitialLoad) {
    return 'full';
  }

  if (input.previousRevisionKey !== input.nextRevisionKey) {
    return 'full';
  }

  const previous = new Set(input.previousVisibleNodeIds);
  const next = new Set(input.nextVisibleNodeIds);

  let added = 0;
  let removed = 0;

  for (const nodeId of next) {
    if (!previous.has(nodeId)) {
      added += 1;
    }
  }
  for (const nodeId of previous) {
    if (!next.has(nodeId)) {
      removed += 1;
    }
  }

  const delta = added + removed;

  if (delta === 0) {
    return 'none';
  }

  if (delta >= FULL_NODE_DELTA_THRESHOLD) {
    return 'full';
  }

  if (delta <= INCREMENTAL_NODE_DELTA_THRESHOLD) {
    return 'incremental';
  }

  return 'incremental';
}
