import { describe, expect, it } from 'vitest';

import {
  buildMediumGraphSnapshot,
  MEDIUM_GRAPH_EDGES_PER_NODE,
  MEDIUM_GRAPH_NODE_COUNT,
  MEDIUM_GRAPH_RUN_ID,
} from '@aegis/graph-domain/fixtures/medium-graph-snapshot';

describe('medium graph fixture generator', () => {
  it('produces deterministic snapshots with expected scale', () => {
    const first = buildMediumGraphSnapshot();
    const second = buildMediumGraphSnapshot();

    expect(second).toEqual(first);
    expect(first.runId).toBe(MEDIUM_GRAPH_RUN_ID);
    expect(first.nodes).toHaveLength(MEDIUM_GRAPH_NODE_COUNT);
    expect(first.edges).toHaveLength(MEDIUM_GRAPH_NODE_COUNT * MEDIUM_GRAPH_EDGES_PER_NODE);
    expect(first.nodes[0]?.id).toBe('asset:node-00000');
    expect(first.nodes.at(-1)?.id).toBe(
      `asset:node-${String(MEDIUM_GRAPH_NODE_COUNT - 1).padStart(5, '0')}`,
    );
  });
});
