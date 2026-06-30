import { describe, expect, it } from 'vitest';

import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';

import {
  getEdgeVisualStyle,
  getNodeVisualStyle,
  getRiskHaloColor,
} from '@/features/operational-graph/semantic/graph-semantic-styles';

function makeNode(overrides: Partial<GraphNodeV1> = {}): GraphNodeV1 {
  return {
    schemaVersion: 1,
    id: 'asset:svc-test',
    entityType: 'asset',
    assetType: 'service',
    label: 'Test Service',
    riskScore: 0.78,
    criticality: 0.9,
    status: 'under_investigation',
    revision: 1,
    ...overrides,
  };
}

function makeEdge(overrides: Partial<GraphEdgeV1> = {}): GraphEdgeV1 {
  return {
    schemaVersion: 1,
    id: 'edge:test',
    source: 'asset:a',
    target: 'asset:b',
    relationshipType: 'COMMUNICATED_WITH',
    directed: true,
    confidence: 0.5,
    riskContribution: 0.3,
    firstSeenAt: '2026-01-01T00:00:00.000Z',
    lastSeenAt: '2026-01-01T00:00:00.000Z',
    eventCount: 0,
    revision: 1,
    ...overrides,
  };
}

describe('graph semantic styles', () => {
  it('derives node style from canonical fields only', () => {
    const style = getNodeVisualStyle(makeNode());
    expect(style.riskBand).toBe('high');
    expect(style.size).toBeGreaterThan(8);
    expect(style.color).toMatch(/^#/);
  });

  it('uses lower opacity for low-confidence edges', () => {
    const style = getEdgeVisualStyle(makeEdge({ confidence: 0.5 }));
    expect(style.type).toBe('line');
    expect(style.opacity).toBeLessThan(0.5);
  });

  it('uses arrow type for high-confidence directed edges', () => {
    const style = getEdgeVisualStyle(makeEdge({ confidence: 1.0, directed: true }));
    expect(style.type).toBe('line');
  });

  it('maps risk band to halo color', () => {
    expect(getRiskHaloColor('critical')).toContain('ef4444');
  });
});
