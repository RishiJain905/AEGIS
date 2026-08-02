import { describe, expect, it } from 'vitest';

import type { GraphEdgeV1, GraphNodeV1 } from '@aegis/contracts-ts';

import {
  getEdgeVisualStyle,
  getNodeSemanticAccent,
  getNodeVisualStyle,
  getRiskHaloColor,
  NEUTRAL_NODE_ACCENT,
  resolveEdgeFlowProfile,
  resolveEdgeFlowStyle,
  resolveEdgeSemanticStyle,
} from '@/features/operational-graph/semantic/graph-semantic-styles';
import { RenderQualityTier } from '@/features/cinematic-graph/contracts/render-quality-tier';

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

    expect(style.color).toBe('#ff6b35');
    expect(style.color).not.toMatch(/rgba|#[0-9a-f]{8}/i);
    expect(style.opacity).toBeGreaterThan(0.5);
    expect(style.opacity).toBeLessThanOrEqual(1);
  });

  it('reserves red for high-risk edges and keeps routine activity calm', () => {
    const routine = getEdgeVisualStyle(
      makeEdge({ confidence: 1, eventCount: 12, riskContribution: 0.1 }),
    );
    const hostile = getEdgeVisualStyle(
      makeEdge({ confidence: 1, eventCount: 12, riskContribution: 0.9 }),
    );
    const idle = getEdgeVisualStyle(makeEdge({ eventCount: 0, riskContribution: 0 }));

    expect(routine.color).toBe('#36a9e1');
    expect(hostile.color).toBe('#ff7078');
    expect(idle.color).toBe('#5d6b7e');
  });

  it('uses arrow type for high-confidence directed edges', () => {
    const style = getEdgeVisualStyle(makeEdge({ confidence: 1.0, directed: true }));
    expect(style.type).toBe('arrow');
  });

  it('maps risk band to halo color from the risk tokens', () => {
    // Dark-theme --aegis-risk-critical token value, with severity alpha.
    expect(getRiskHaloColor('critical')).toBe('#ff707888');
    expect(getRiskHaloColor('high')).toBe('#ff6b3566');
  });
});

describe('node semantic accent (§7.1)', () => {
  it('prefers status over risk when both signal', () => {
    const accent = getNodeSemanticAccent({ status: 'compromised', riskScore: 0.9 });
    expect(accent.source).toBe('status');
    expect(accent.emissiveColor).toBe('#ff7078');
  });

  it('falls back to the risk band color for normal-status elevated risk', () => {
    const accent = getNodeSemanticAccent({ status: 'normal', riskScore: 0.78 });
    expect(accent.source).toBe('risk');
    expect(accent.emissiveColor).toBe('#ff6b35');
  });

  it('keeps a quiet neutral accent for no-signal nodes', () => {
    const accent = getNodeSemanticAccent({ status: 'normal', riskScore: 0.05 });
    expect(accent.source).toBe('none');
    expect(accent.emissiveColor).toBe(NEUTRAL_NODE_ACCENT);
  });
});

describe('shared edge semantic style (§7.4)', () => {
  it('dashes only incident-scope highlighted edges', () => {
    const incident = resolveEdgeSemanticStyle({
      edge: makeEdge(),
      highlighted: true,
      dimmed: false,
      highlightKind: 'incident',
    });
    expect(incident.dashed).toBe(true);
    expect(incident.color).toBe('#ef4444');
    expect(incident.opacity).toBe(1);

    const path = resolveEdgeSemanticStyle({
      edge: makeEdge(),
      highlighted: true,
      dimmed: false,
      highlightKind: 'path',
    });
    expect(path.dashed).toBe(false);
    expect(path.color).toBe('#f59e0b');
  });

  it('keeps default edges thin and muted and doubles highlighted width', () => {
    const edge = makeEdge({ confidence: 0.8 });
    const base = resolveEdgeSemanticStyle({
      edge,
      highlighted: false,
      dimmed: false,
      highlightKind: null,
    });
    const highlighted = resolveEdgeSemanticStyle({
      edge,
      highlighted: true,
      dimmed: false,
      highlightKind: 'neighborhood',
    });
    expect(highlighted.width).toBe(base.width * 2);
    expect(base.opacity).toBeLessThan(highlighted.opacity);
  });
});

describe('edge flow gating (§7.9)', () => {
  it('renders fully static under prefers-reduced-motion regardless of tier', () => {
    expect(resolveEdgeFlowProfile(RenderQualityTier.HIGH, true)).toBe('static');
    expect(resolveEdgeFlowProfile(RenderQualityTier.MEDIUM, true)).toBe('static');
  });

  it('converges LOW and FALLBACK_2D tiers on the same static endpoint', () => {
    expect(resolveEdgeFlowProfile(RenderQualityTier.LOW, false)).toBe('static');
    expect(resolveEdgeFlowProfile(RenderQualityTier.FALLBACK_2D, false)).toBe('static');
  });

  it('maps HIGH to full flow and MEDIUM to the coarse variant', () => {
    expect(resolveEdgeFlowProfile(RenderQualityTier.HIGH, false)).toBe('full');
    expect(resolveEdgeFlowProfile(RenderQualityTier.MEDIUM, false)).toBe('coarse');
  });

  it('animates directed edges only, muted by default and brighter when highlighted', () => {
    expect(resolveEdgeFlowStyle({ directed: false, highlighted: false, dimmed: false })).toBeNull();
    expect(resolveEdgeFlowStyle({ directed: true, highlighted: false, dimmed: true })).toBeNull();
    const muted = resolveEdgeFlowStyle({ directed: true, highlighted: false, dimmed: false });
    const active = resolveEdgeFlowStyle({ directed: true, highlighted: true, dimmed: false });
    if (muted === null || active === null) {
      throw new Error('expected flow styles for directed undimmed edges');
    }
    expect(active.speed).toBeGreaterThan(muted.speed);
    expect(active.amplitude).toBeGreaterThan(muted.amplitude);
  });
});
