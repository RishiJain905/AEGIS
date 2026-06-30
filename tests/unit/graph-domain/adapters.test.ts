import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot } from './helpers';

describe('canonical adapters', () => {
  it('round-trips snapshot preserving ids and revisions', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);
    const exported = store.exportSnapshot();

    expect(exported.runId).toBe(snapshot.runId);
    expect(exported.nodes.map((n) => n.id)).toEqual(
      [...snapshot.nodes].sort((a, b) => a.id.localeCompare(b.id)).map((n) => n.id),
    );
    expect(exported.edges.map((e) => e.id)).toEqual(
      [...snapshot.edges].sort((a, b) => a.id.localeCompare(b.id)).map((e) => e.id),
    );
  });
});
