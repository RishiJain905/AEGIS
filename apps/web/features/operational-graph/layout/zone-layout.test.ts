import { describe, expect, it } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import {
  computeZoneLayout,
  zoneConstraintsFromLayout,
  zoneLabelFromClusterId,
} from '@/features/operational-graph/layout/zone-layout';

function makeNode(id: string, clusterId?: string, criticality = 0.5): GraphNodeV1 {
  return {
    schemaVersion: 1,
    id,
    entityType: 'asset',
    assetType: 'service',
    label: id,
    clusterId,
    riskScore: 0.2,
    criticality,
    status: 'normal',
    revision: 1,
  };
}

/** Eight zones of five nodes — the Operation Silent Relay shape. */
function silentRelayShapedNodes(): GraphNodeV1[] {
  const zones = [
    'business-unit:logistics',
    'business-unit:communications',
    'business-unit:identity',
    'business-unit:cloud',
    'business-unit:endpoints',
    'business-unit:data-platform',
    'business-unit:security-ops',
    'business-unit:ai-ops',
  ];
  return zones.flatMap((zone, zoneIndex) =>
    Array.from({ length: 5 }, (_, nodeIndex) =>
      makeNode(`asset:z${String(zoneIndex)}-n${String(nodeIndex)}`, zone, 0.9 - nodeIndex * 0.1),
    ),
  );
}

describe('computeZoneLayout', () => {
  it('is deterministic across runs', () => {
    const nodes = silentRelayShapedNodes();
    const first = computeZoneLayout(nodes, []);
    const second = computeZoneLayout(nodes, []);
    expect(first.positions).toEqual(second.positions);
    expect(first.zones).toEqual(second.zones);
  });

  it('never overlaps nodes — every pair keeps readable spacing', () => {
    const { positions } = computeZoneLayout(silentRelayShapedNodes(), []);
    const entries = Object.values(positions);
    expect(entries).toHaveLength(40);
    for (let i = 0; i < entries.length; i += 1) {
      for (let j = i + 1; j < entries.length; j += 1) {
        const a = entries[i];
        const b = entries[j];
        if (!a || !b) {
          continue;
        }
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(50);
      }
    }
  });

  it('keeps every node inside its own zone constraint disc', () => {
    const nodes = silentRelayShapedNodes();
    const { positions, zones } = computeZoneLayout(nodes, []);
    const constraints = zoneConstraintsFromLayout(zones);

    for (const node of nodes) {
      const zoneId = node.clusterId ?? 'unclustered';
      const constraint = constraints[zoneId];
      const position = positions[node.id];
      expect(constraint).toBeDefined();
      expect(position).toBeDefined();
      if (!constraint || !position) {
        continue;
      }
      const distance = Math.hypot(position.x - constraint.x, position.y - constraint.y);
      expect(distance).toBeLessThanOrEqual(constraint.radius + 1e-6);
    }
  });

  it('separates zones so sectors never share territory', () => {
    const nodes = silentRelayShapedNodes();
    const { positions } = computeZoneLayout(nodes, []);

    for (const left of nodes) {
      for (const right of nodes) {
        if (left.clusterId === right.clusterId) {
          continue;
        }
        const a = positions[left.id];
        const b = positions[right.id];
        if (!a || !b) {
          continue;
        }
        // Cross-zone pairs must stay far beyond intra-zone spacing.
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(180);
      }
    }
  });

  it('places the most critical asset at the zone center', () => {
    const nodes = [
      makeNode('asset:minor', 'zone:a', 0.2),
      makeNode('asset:crown-jewel', 'zone:a', 0.95),
      makeNode('asset:mid', 'zone:a', 0.5),
    ];
    const { positions, zones } = computeZoneLayout(nodes, []);
    const zone = zones[0];
    const center = positions['asset:crown-jewel'];
    expect(zone).toBeDefined();
    expect(center).toBeDefined();
    if (!zone || !center) {
      return;
    }
    expect(center.x).toBeCloseTo(zone.center.x);
    expect(center.y).toBeCloseTo(zone.center.y);
  });

  it('preserves existing positions while keeping zone geometry stable', () => {
    const nodes = silentRelayShapedNodes();
    const initial = computeZoneLayout(nodes, []);
    const pinned = { 'asset:z0-n0': { x: 9999, y: 9999 } };
    const next = computeZoneLayout(nodes, [], pinned);

    expect(next.positions['asset:z0-n0']).toEqual({ x: 9999, y: 9999 });
    expect(next.zones).toEqual(initial.zones);
    expect(next.positions['asset:z3-n2']).toEqual(initial.positions['asset:z3-n2']);
  });

  it('prefers cluster metadata labels and derives readable fallbacks', () => {
    const nodes = [makeNode('asset:a', 'business-unit:ai-ops')];
    const withMeta = computeZoneLayout(nodes, [
      {
        schemaVersion: 1,
        id: 'business-unit:ai-ops',
        label: 'AI Operations',
        memberNodeIds: ['asset:a'],
        revision: 1,
      },
    ]);
    expect(withMeta.zones[0]?.label).toBe('AI Operations');

    const withoutMeta = computeZoneLayout(nodes, []);
    expect(withoutMeta.zones[0]?.label).toBe('AI OPS');
  });

  it('groups unclustered nodes into an UNZONED sector', () => {
    const { zones } = computeZoneLayout([makeNode('asset:stray')], []);
    expect(zones).toHaveLength(1);
    expect(zones[0]?.id).toBe('unclustered');
    expect(zones[0]?.label).toBe('UNZONED');
  });
});

describe('zoneLabelFromClusterId', () => {
  it('uppercases and strips the namespace prefix', () => {
    expect(zoneLabelFromClusterId('business-unit:security-ops')).toBe('SECURITY OPS');
    expect(zoneLabelFromClusterId('business-unit:data-platform')).toBe('DATA PLATFORM');
    expect(zoneLabelFromClusterId('plain')).toBe('PLAIN');
  });
});
