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

  it('keeps edge color opaque and represents activity alpha as opacity', () => {
    const style = getEdgeVisualStyle(
      makeEdge({ confidence: 1, eventCount: 12, riskContribution: 0.65 }),
    );

    expect(style.color).toBe('#ef4444');
    expect(style.color).not.toMatch(/rgba|#[0-9a-f]{8}/i);
    expect(style.opacity).toBeGreaterThan(0.5);
    expect(style.opacity).toBeLessThanOrEqual(1);
  });

  it('uses arrow type for high-confidence directed edges', () => {
    const style = getEdgeVisualStyle(makeEdge({ confidence: 1.0, directed: true }));
    expect(style.type).toBe('arrow');
  });

  it('maps risk band to halo color', () => {
    expect(getRiskHaloColor('critical')).toContain('ef4444');
  });
});
