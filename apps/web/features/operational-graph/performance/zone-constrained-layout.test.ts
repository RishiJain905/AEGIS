import { describe, expect, it } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import {
  defaultLayoutWorkerSettings,
  type LayoutWorkerRequest,
} from '@/features/operational-graph/contracts/layout-worker-protocol';
import {
  computeZoneLayout,
  zoneConstraintsFromLayout,
} from '@/features/operational-graph/layout/zone-layout';
import { runForceAtlas2 } from '../../../workers/layout/force-atlas2-runner';

function makeNode(id: string, clusterId: string, criticality = 0.5): GraphNodeV1 {
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

/** 38-node board across 8 zones with cross-zone links — the exact shape that
 * used to collapse into a central hairball under unconstrained ForceAtlas2. */
function buildRequest(): { request: LayoutWorkerRequest; nodes: GraphNodeV1[] } {
  const zoneIds = [
    'business-unit:logistics',
    'business-unit:communications',
    'business-unit:identity',
    'business-unit:cloud',
    'business-unit:endpoints',
    'business-unit:data-platform',
    'business-unit:security-ops',
    'business-unit:ai-ops',
  ];
  const nodes: GraphNodeV1[] = [];
  zoneIds.forEach((zoneId, zoneIndex) => {
    const count = zoneIndex < 6 ? 5 : 4;
    for (let i = 0; i < count; i += 1) {
      nodes.push(makeNode(`asset:z${String(zoneIndex)}-n${String(i)}`, zoneId, 0.9 - i * 0.12));
    }
  });

  const edges: LayoutWorkerRequest['edges'] = [];
  // Intra-zone spine plus cross-zone lateral-movement links between every
  // consecutive zone pair — the pulls that previously merged the board.
  zoneIds.forEach((_, zoneIndex) => {
    const count = zoneIndex < 6 ? 5 : 4;
    for (let i = 1; i < count; i += 1) {
      edges.push({
        source: `asset:z${String(zoneIndex)}-n0`,
        target: `asset:z${String(zoneIndex)}-n${String(i)}`,
        weight: 1,
      });
    }
    if (zoneIndex > 0) {
      edges.push({
        source: `asset:z${String(zoneIndex - 1)}-n0`,
        target: `asset:z${String(zoneIndex)}-n0`,
        weight: 1.5,
      });
    }
  });

  const layout = computeZoneLayout(nodes, []);
  const request: LayoutWorkerRequest = {
    protocolVersion: 1,
    requestId: 'layout-req-test',
    graphRevision: { schemaVersion: 1, runId: 'run_test', sequence: 1, revision: 1 },
    runId: 'run_test',
    mode: 'full',
    nodes: nodes.map((node) => ({
      id: node.id,
      clusterId: node.clusterId ?? null,
      pinned: false,
    })),
    edges,
    seedPositions: layout.positions,
    zoneConstraints: zoneConstraintsFromLayout(layout.zones),
    settings: defaultLayoutWorkerSettings,
  };
  return { request, nodes };
}

describe('zone-constrained ForceAtlas2', () => {
  it('keeps every node inside its zone disc — no central hairball', () => {
    const { request, nodes } = buildRequest();
    const { positions } = runForceAtlas2(request, () => false);

    const constraints = request.zoneConstraints ?? {};
    for (const node of nodes) {
      const constraint = node.clusterId ? constraints[node.clusterId] : undefined;
      const position = positions[node.id];
      expect(constraint).toBeDefined();
      expect(position).toBeDefined();
      if (!constraint || !position) {
        continue;
      }
      const distance = Math.hypot(position.x - constraint.x, position.y - constraint.y);
      expect(distance).toBeLessThanOrEqual(constraint.radius + 1);
    }
  });

  it('keeps nodes readably separated after refinement', () => {
    const { request } = buildRequest();
    const { positions } = runForceAtlas2(request, () => false);
    const entries: { x: number; y: number }[] = Object.values(positions);

    for (let i = 0; i < entries.length; i += 1) {
      for (let j = i + 1; j < entries.length; j += 1) {
        const a = entries[i];
        const b = entries[j];
        if (!a || !b) {
          continue;
        }
        // 2×OVERLAP_RADIUS is the guarantee; allow slack for the final
        // containment clamp pulling boundary nodes slightly together.
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(30);
      }
    }
  });

  it('is deterministic for identical requests', () => {
    const first = runForceAtlas2(buildRequest().request, () => false);
    const second = runForceAtlas2(buildRequest().request, () => false);
    expect(first.positions).toEqual(second.positions);
  });
});
