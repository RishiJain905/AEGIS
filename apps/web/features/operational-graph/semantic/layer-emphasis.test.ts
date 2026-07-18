import { describe, expect, it } from 'vitest';

import { GraphLayer } from '@aegis/graph-domain';

import { computeLayerEmphasis } from './layer-emphasis';

function node(
  id: string,
  overrides: Partial<{
    entityType: 'asset' | 'cluster';
    assetType: string;
    riskScore: number;
    status: string;
  }> = {},
) {
  return {
    id,
    entityType: overrides.entityType ?? 'asset',
    assetType: overrides.assetType ?? 'service',
    riskScore: overrides.riskScore ?? 0,
    status: overrides.status ?? 'normal',
  };
}

function edge(
  id: string,
  source: string,
  target: string,
  overrides: Partial<{ eventCount: number; riskContribution: number }> = {},
) {
  return {
    id,
    source,
    target,
    eventCount: overrides.eventCount ?? 0,
    riskContribution: overrides.riskContribution ?? 0,
  };
}

const ALL_LAYERS = [
  GraphLayer.INFRASTRUCTURE,
  GraphLayer.ACTIVITY,
  GraphLayer.SECURITY_STATE,
  GraphLayer.INVESTIGATION,
  GraphLayer.PRESENTATION,
];

describe('computeLayerEmphasis', () => {
  it('dims nothing when every layer is enabled', () => {
    const emphasis = computeLayerEmphasis(
      {
        nodes: [node('asset:a'), node('asset:b', { assetType: 'user' })],
        edges: [edge('edge:ab', 'asset:a', 'asset:b')],
      },
      ALL_LAYERS,
    );
    expect(emphasis.dimmedNodeIds.size).toBe(0);
    expect(emphasis.dimmedEdgeIds.size).toBe(0);
  });

  it('dims quiet infrastructure when the infrastructure layer is disabled', () => {
    const emphasis = computeLayerEmphasis(
      {
        nodes: [node('asset:quiet'), node('asset:risky', { riskScore: 0.8, status: 'suspicious' })],
        edges: [],
      },
      ALL_LAYERS.filter((layer) => layer !== GraphLayer.INFRASTRUCTURE),
    );
    expect(emphasis.dimmedNodeIds.has('asset:quiet')).toBe(true);
    expect(emphasis.dimmedNodeIds.has('asset:risky')).toBe(false);
  });

  it('dims activity edges when the activity layer is disabled but keeps structural edges', () => {
    const emphasis = computeLayerEmphasis(
      {
        nodes: [node('asset:a'), node('asset:b')],
        edges: [
          edge('edge:active', 'asset:a', 'asset:b', { eventCount: 12 }),
          edge('edge:structural', 'asset:a', 'asset:b'),
        ],
      },
      [GraphLayer.INFRASTRUCTURE, GraphLayer.PRESENTATION],
    );
    expect(emphasis.dimmedEdgeIds.has('edge:active')).toBe(true);
    expect(emphasis.dimmedEdgeIds.has('edge:structural')).toBe(false);
  });

  it('keeps identity-plane assets on the base plane instead of always dimming them', () => {
    const emphasis = computeLayerEmphasis(
      {
        nodes: [node('asset:user', { assetType: 'user' })],
        edges: [],
      },
      ALL_LAYERS,
    );
    expect(emphasis.dimmedNodeIds.has('asset:user')).toBe(false);
  });

  it('dims edges whose endpoint is dimmed', () => {
    const emphasis = computeLayerEmphasis(
      {
        nodes: [node('asset:quiet'), node('asset:hot', { riskScore: 0.9 })],
        edges: [edge('edge:qh', 'asset:quiet', 'asset:hot', { riskContribution: 0.5 })],
      },
      [GraphLayer.SECURITY_STATE],
    );
    expect(emphasis.dimmedNodeIds.has('asset:quiet')).toBe(true);
    expect(emphasis.dimmedEdgeIds.has('edge:qh')).toBe(true);
  });
});
