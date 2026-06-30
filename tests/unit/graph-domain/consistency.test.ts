import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot, loadGraphSnapshotFixture } from './helpers';

describe('graph consistency', () => {
  it('reports valid state for connected snapshot', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    const report = store.validateConsistency();
    expect(report.valid).toBe(true);
    expect(report.issues).toHaveLength(0);
  });

  it('does not load edges with missing endpoints from contract fixture snapshot', () => {
    const store = createGraphStore();
    store.loadSnapshot(
      loadGraphSnapshotFixture('tests/contract/fixtures/valid/graph_snapshot_v1.json'),
    );
    expect(store.exportSnapshot().edges).toHaveLength(0);
    expect(store.exportSnapshot().nodes).toHaveLength(1);
    const report = store.validateConsistency();
    expect(report.issues.some((issue) => issue.code === 'UNRESOLVED_CLUSTER_REFERENCE')).toBe(true);
  });

  it('detects missing cluster members', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    snapshot.clusters = [
      {
        schemaVersion: 1,
        id: 'business-unit:missing',
        label: 'Missing',
        memberNodeIds: ['asset:missing-node'],
        revision: 1,
      },
    ];
    store.loadSnapshot(snapshot);
    const report = store.validateConsistency();
    expect(report.issues.some((issue) => issue.code === 'CLUSTER_MEMBER_MISSING')).toBe(true);
  });
});
