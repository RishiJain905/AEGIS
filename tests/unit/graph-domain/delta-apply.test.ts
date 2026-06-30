import { describe, expect, it } from 'vitest';

import { GraphDeltaApplyStatus, GraphDomainErrorCode, createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot, loadGraphDeltaFixture } from './helpers';

describe('graph delta application', () => {
  it('applies a valid next-sequence delta', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);

    const delta = loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json');
    const adjustedDelta = {
      ...delta,
      sequence: snapshot.sequence + 1,
      revision: snapshot.revision + 1,
      node: delta.node
        ? {
            ...delta.node,
            id: 'asset:svc-a',
            revision: 2,
          }
        : undefined,
    };

    const result = store.applyDelta(adjustedDelta);
    expect(result.status).toBe(GraphDeltaApplyStatus.APPLIED);
    expect(store.getLastAppliedSequence()).toBe(snapshot.sequence + 1);
    expect(store.exportSnapshot().nodes.find((n) => n.id === 'asset:svc-a')?.revision).toBe(2);
  });

  it('treats duplicate sequence as idempotent without mutation', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);
    const before = store.exportSnapshot();

    const delta = {
      ...loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json'),
      sequence: snapshot.sequence,
      revision: snapshot.revision + 99,
    };

    const result = store.applyDelta(delta);
    expect(result.status).toBe(GraphDeltaApplyStatus.DUPLICATE);
    expect(result.errorCode).toBe(GraphDomainErrorCode.GRAPH_DUPLICATE_DELTA);
    expect(store.exportSnapshot()).toEqual(before);
  });

  it('rejects sequence gaps without mutating state', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);
    const before = store.exportSnapshot();

    const result = store.applyDelta({
      ...loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json'),
      sequence: snapshot.sequence + 2,
      revision: snapshot.revision + 1,
    });

    expect(result.status).toBe(GraphDeltaApplyStatus.GAP_DETECTED);
    expect(result.errorCode).toBe(GraphDomainErrorCode.GRAPH_SEQUENCE_GAP);
    expect(store.exportSnapshot()).toEqual(before);
    expect(store.getLastAppliedSequence()).toBe(snapshot.sequence);
  });

  it('rejects stale revisions', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const stale = {
      ...loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json'),
      sequence: 11,
      revision: 2,
      node: {
        schemaVersion: 1 as const,
        id: 'asset:svc-a',
        entityType: 'asset' as const,
        assetType: 'service' as const,
        label: 'Stale',
        riskScore: 0.1,
        criticality: 0.1,
        status: 'normal' as const,
        revision: 0,
      },
    };

    const result = store.applyDelta(stale);
    expect(result.status).toBe(GraphDeltaApplyStatus.REJECTED);
    expect(result.errorCode).toBe(GraphDomainErrorCode.GRAPH_STALE_REVISION);
  });

  it('stops batch apply after gap or rejection', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);

    const results = store.applyDeltas([
      {
        ...loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json'),
        sequence: snapshot.sequence + 2,
        revision: 2,
      },
      {
        ...loadGraphDeltaFixture('tests/contract/fixtures/valid/graph_delta_v1.json'),
        sequence: snapshot.sequence + 3,
        revision: 3,
      },
    ]);

    expect(results).toHaveLength(1);
    expect(results[0]?.status).toBe(GraphDeltaApplyStatus.GAP_DETECTED);
  });
});
