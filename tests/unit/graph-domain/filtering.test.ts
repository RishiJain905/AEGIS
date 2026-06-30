import { describe, expect, it } from 'vitest';

import { GraphLayer, createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot } from './helpers';

describe('graph filtering', () => {
  it('hides nodes by layer without deleting canonical state', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    const before = store.exportSnapshot();

    const filtered = store.applyFilters({
      enabledLayers: [GraphLayer.INVESTIGATION],
    });

    expect(filtered.visibleNodeIds).toEqual(['asset:svc-b']);
    expect(store.exportSnapshot()).toEqual(before);
  });

  it('supports presentation-layer hidden id lists', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const filtered = store.applyFilters({
      enabledLayers: [
        GraphLayer.INFRASTRUCTURE,
        GraphLayer.ACTIVITY,
        GraphLayer.SECURITY_STATE,
        GraphLayer.INVESTIGATION,
        GraphLayer.PRESENTATION,
      ],
      hiddenNodeIds: ['asset:svc-b'],
    });

    expect(filtered.visibleNodeIds).not.toContain('asset:svc-b');
    expect(store.exportSnapshot().nodes).toHaveLength(3);
  });
});
