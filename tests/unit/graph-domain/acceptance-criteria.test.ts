import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { createGraphStore } from '@aegis/graph-domain';

import { buildConnectedSnapshot } from './helpers';

describe('Phase 05 acceptance criteria', () => {
  it('duplicate or out-of-order deltas cannot silently corrupt state', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());
    const baseline = store.exportSnapshot();

    const gap = store.applyDelta({
      schemaVersion: 1,
      runId: baseline.runId,
      sequence: baseline.sequence + 2,
      revision: baseline.revision + 1,
      operation: 'delete_node',
      targetId: 'asset:svc-a',
    });
    expect(gap.status).toBe('gap_detected');
    expect(store.exportSnapshot()).toEqual(baseline);

    const duplicate = store.applyDelta({
      schemaVersion: 1,
      runId: baseline.runId,
      sequence: baseline.sequence,
      revision: baseline.revision + 5,
      operation: 'delete_node',
      targetId: 'asset:svc-b',
    });
    expect(duplicate.status).toBe('duplicate');
    expect(store.exportSnapshot()).toEqual(baseline);
  });

  it('algorithms return deterministic explainable results', () => {
    const store = createGraphStore();
    store.loadSnapshot(buildConnectedSnapshot());

    const first = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:device-c',
      targetId: 'asset:svc-b',
      maxHops: 4,
      relationshipTypes: [],
      directedOnly: true,
    });
    const second = store.queryPaths({
      schemaVersion: 1,
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      sourceId: 'asset:device-c',
      targetId: 'asset:svc-b',
      maxHops: 4,
      relationshipTypes: [],
      directedOnly: true,
    });

    expect(second).toEqual(first);
    expect(first.explanation.pathsConsidered).toBeGreaterThan(0);
  });

  it('package has no React or renderer dependency', () => {
    const pkg = JSON.parse(
      readFileSync(new URL('../../../packages/graph-domain/package.json', import.meta.url), 'utf8'),
    ) as { dependencies?: Record<string, string> };
    const deps = Object.keys(pkg.dependencies ?? {});
    expect(deps).not.toContain('react');
    expect(deps).not.toContain('sigma');
    expect(deps).not.toContain('three');
    expect(deps).toContain('graphology');
  });

  it('same semantic graph can feed analysis via exportSnapshot', () => {
    const store = createGraphStore();
    const snapshot = buildConnectedSnapshot();
    store.loadSnapshot(snapshot);

    store.applyDelta({
      schemaVersion: 1,
      runId: snapshot.runId,
      sequence: snapshot.sequence + 1,
      revision: snapshot.revision + 1,
      operation: 'upsert_node',
      node: {
        ...snapshot.nodes[0]!,
        label: 'Updated for replay',
        revision: 2,
      },
    });

    const exported = store.exportSnapshot();
    expect(exported.nodes.find((n) => n.id === 'asset:svc-a')?.label).toBe('Updated for replay');
    expect(exported.sequence).toBe(snapshot.sequence + 1);
  });
});
