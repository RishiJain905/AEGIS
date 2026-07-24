import type { GraphNodeV1 } from '@aegis/contracts-ts';

export interface NodeRevealState {
  disclosed: boolean;
  status: GraphNodeV1['status'];
}

/**
 * The detection beat, derived purely from consecutive snapshots. A node earns
 * a reveal pulse when either:
 * - the fog of war lifts on a hostile asset (disclosed flips false -> true
 *   while its status is not `normal`), or
 * - a visible asset escalates from `normal` to `suspicious`/`compromised`
 *   (live detections without fog fields).
 * The first snapshot seeds state without firing, so arriving mid-run does not
 * light up the whole board.
 */
export function detectRevealTransitions(
  previous: ReadonlyMap<string, NodeRevealState> | null,
  nodes: readonly GraphNodeV1[],
): { revealedNodeIds: string[]; nextState: Map<string, NodeRevealState> } {
  const nextState = new Map<string, NodeRevealState>();
  const revealedNodeIds: string[] = [];

  for (const node of nodes) {
    const disclosed = node.disclosed !== false;
    nextState.set(node.id, { disclosed, status: node.status });
    if (!previous) {
      continue;
    }
    const before = previous.get(node.id);
    if (!before) {
      continue;
    }
    const fogLifted = !before.disclosed && disclosed && node.status !== 'normal';
    const escalated =
      before.status === 'normal' &&
      (node.status === 'compromised' || node.status === 'suspicious');
    if (fogLifted || escalated) {
      revealedNodeIds.push(node.id);
    }
  }

  return { revealedNodeIds, nextState };
}
