import { describe, expect, it } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import {
  assetTypeBand,
  computeZoneLayout,
  deriveZoneLabel,
  hoverHeight,
  platformRadius,
  ZONE_UNASSIGNED_ID,
  zoneAlertLevel,
} from './zone-layout';

let counter = 0;
function makeNode(overrides: Partial<GraphNodeV1> = {}): GraphNodeV1 {
  counter += 1;
  return {
    schemaVersion: 1,
    id: `asset:node-${String(counter).padStart(3, '0')}`,
    entityType: 'asset',
    assetType: 'service',
    label: `Node ${String(counter)}`,
    clusterId: 'business-unit:cloud',
    riskScore: 0.1,
    criticality: 0.5,
    status: 'normal',
    revision: 0,
    ...overrides,
  } as GraphNodeV1;
}

function eightZoneFixture(): GraphNodeV1[] {
  const zones = [
    'business-unit:ai-ops',
    'business-unit:cloud',
    'business-unit:communications',
    'business-unit:data-platform',
    'business-unit:endpoints',
    'business-unit:identity',
    'business-unit:logistics',
    'business-unit:security-ops',
  ];
  const nodes: GraphNodeV1[] = [];
  for (const zone of zones) {
    nodes.push(
      makeNode({ clusterId: zone, assetType: 'database', criticality: 0.9 }),
      makeNode({ clusterId: zone, assetType: 'service' }),
      makeNode({ clusterId: zone, assetType: 'service' }),
      makeNode({ clusterId: zone, assetType: 'device', criticality: 0.2 }),
      makeNode({ clusterId: zone, assetType: 'identity' }),
    );
  }
  return nodes;
}

describe('computeZoneLayout', () => {
  it('is deterministic for the same input', () => {
    const nodes = eightZoneFixture();
    const first = computeZoneLayout(nodes);
    const second = computeZoneLayout([...nodes].reverse());
    expect(second.positions).toEqual(first.positions);
    expect(second.zones).toEqual(first.zones);
  });

  it('creates one platform per cluster and keeps every node on its own platform', () => {
    const nodes = eightZoneFixture();
    const layout = computeZoneLayout(nodes);
    expect(layout.zones).toHaveLength(8);

    for (const zone of layout.zones) {
      for (const nodeId of zone.nodeIds) {
        const position = layout.positions[nodeId];
        expect(position).toBeDefined();
        const distance = Math.hypot(
          (position?.x ?? 0) - zone.center.x,
          (position?.z ?? 0) - zone.center.z,
        );
        expect(distance).toBeLessThanOrEqual(zone.radius);
      }
    }
  });

  it('keeps platforms from overlapping', () => {
    const layout = computeZoneLayout(eightZoneFixture());
    for (let i = 0; i < layout.zones.length; i += 1) {
      for (let j = i + 1; j < layout.zones.length; j += 1) {
        const a = layout.zones[i];
        const b = layout.zones[j];
        if (!a || !b) {
          continue;
        }
        const distance = Math.hypot(a.center.x - b.center.x, a.center.z - b.center.z);
        expect(distance).toBeGreaterThan(a.radius + b.radius);
      }
    }
  });

  it('stratifies crown jewels closer to the platform core than endpoints', () => {
    const zone = 'business-unit:data-platform';
    const nodes = [
      makeNode({ clusterId: zone, assetType: 'database' }),
      makeNode({ clusterId: zone, assetType: 'database' }),
      makeNode({ clusterId: zone, assetType: 'device' }),
      makeNode({ clusterId: zone, assetType: 'device' }),
      makeNode({ clusterId: zone, assetType: 'device' }),
    ];
    const layout = computeZoneLayout(nodes);
    const platform = layout.zones[0];
    expect(platform).toBeDefined();

    const radial = (id: string) => {
      const position = layout.positions[id];
      return Math.hypot(
        (position?.x ?? 0) - (platform?.center.x ?? 0),
        (position?.z ?? 0) - (platform?.center.z ?? 0),
      );
    };
    const maxDatabase = Math.max(...nodes.slice(0, 2).map((node) => radial(node.id)));
    const minDevice = Math.min(...nodes.slice(2).map((node) => radial(node.id)));
    expect(maxDatabase).toBeLessThan(minDevice);
  });

  it('maps criticality to hover height', () => {
    const low = makeNode({ criticality: 0 });
    const high = makeNode({ criticality: 1 });
    const layout = computeZoneLayout([low, high]);
    expect(layout.positions[low.id]?.y).toBeCloseTo(hoverHeight(0), 5);
    expect(layout.positions[high.id]?.y).toBeCloseTo(hoverHeight(1), 5);
    expect(hoverHeight(1)).toBeGreaterThan(hoverHeight(0));
  });

  it('places unzoned nodes on a central platform inside the ring', () => {
    const nodes = [
      ...eightZoneFixture(),
      makeNode({ clusterId: undefined }),
      makeNode({ clusterId: undefined }),
    ];
    const layout = computeZoneLayout(nodes);
    const central = layout.zones.find((zone) => zone.id === ZONE_UNASSIGNED_ID);
    expect(central).toBeDefined();
    expect(central?.center.x).toBe(0);
    expect(central?.center.z).toBe(0);

    const ringZones = layout.zones.filter((zone) => zone.id !== ZONE_UNASSIGNED_ID);
    for (const zone of ringZones) {
      const distance = Math.hypot(zone.center.x, zone.center.z);
      expect(distance).toBeGreaterThan((central?.radius ?? 0) + zone.radius);
    }
  });

  it('keeps the whole theater inside a bounded world span', () => {
    const layout = computeZoneLayout(eightZoneFixture());
    const xs = Object.values(layout.positions).map((position) => position.x);
    const zs = Object.values(layout.positions).map((position) => position.z);
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThanOrEqual(1_600);
    expect(Math.max(...zs) - Math.min(...zs)).toBeLessThanOrEqual(1_600);
  });
});

describe('helpers', () => {
  it('bands asset types core → outer', () => {
    expect(assetTypeBand('database')).toBe(0);
    expect(assetTypeBand('ai_model')).toBe(0);
    expect(assetTypeBand('service')).toBe(1);
    expect(assetTypeBand('control')).toBe(1);
    expect(assetTypeBand('device')).toBe(2);
    expect(assetTypeBand('user')).toBe(2);
    expect(assetTypeBand(null)).toBe(2);
  });

  it('derives readable zone labels with cluster labels winning', () => {
    expect(
      deriveZoneLabel('business-unit:security-ops', [
        {
          schemaVersion: 1,
          id: 'business-unit:security-ops',
          label: 'Security Operations',
          memberNodeIds: [],
          revision: 0,
        },
      ]),
    ).toBe('Security Operations');
    expect(deriveZoneLabel('business-unit:security-ops', [])).toBe('security ops');
    expect(deriveZoneLabel(ZONE_UNASSIGNED_ID, [])).toBe('Unassigned');
  });

  it('grows platforms with member count within bounds', () => {
    expect(platformRadius(1)).toBeGreaterThanOrEqual(46);
    expect(platformRadius(50)).toBeLessThanOrEqual(124);
    expect(platformRadius(9)).toBeGreaterThan(platformRadius(2));
  });

  it('rolls zone statuses up with active threat outranking containment', () => {
    expect(zoneAlertLevel([])).toBe('calm');
    expect(zoneAlertLevel(['normal', 'normal'])).toBe('calm');
    expect(zoneAlertLevel(['normal', 'contained'])).toBe('guarded');
    expect(zoneAlertLevel(['contained', 'suspicious'])).toBe('elevated');
    expect(zoneAlertLevel(['under_investigation'])).toBe('elevated');
    expect(zoneAlertLevel(['suspicious', 'compromised', 'contained'])).toBe('critical');
  });
});
