import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';
import { ContractValidationError } from '@aegis/contracts-ts';

import { buildConnectedSnapshot, loadGraphSnapshotFixture } from './helpers';

describe('snapshot load', () => {
  it('loads a valid contract fixture snapshot', () => {
    const store = createGraphStore();
    const snapshot = loadGraphSnapshotFixture(
      'tests/contract/fixtures/valid/graph_snapshot_v1.json',
    );
    store.loadSnapshot(snapshot);
    expect(store.getRunId()).toBe(snapshot.runId);
    expect(store.getLastAppliedSequence()).toBe(snapshot.sequence);
    expect(store.exportSnapshot().nodes).toHaveLength(snapshot.nodes.length);
  });

  it('loads a connected multi-node snapshot', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    expect(store.exportSnapshot().nodes).toHaveLength(3);
    expect(store.exportSnapshot().edges).toHaveLength(2);
  });

  it('fails closed on invalid snapshot input', () => {
    const store = createGraphStore();
    expect(() =>
      store.loadSnapshot({
        schemaVersion: 1,
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        sequence: 1,
        capturedAt: '2026-06-30T00:00:00.000Z',
        nodes: [],
        edges: [],
        clusters: [],
        revision: 1,
      } as never),
    ).not.toThrow();

    expect(() => store.loadSnapshot({ invalid: true } as never)).toThrow(ContractValidationError);
  });
});
