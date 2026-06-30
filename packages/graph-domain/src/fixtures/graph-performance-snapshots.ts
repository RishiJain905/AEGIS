import type {
  GraphClusterV1,
  GraphEdgeV1,
  GraphNodeV1,
  GraphSnapshotV1,
} from '@aegis/contracts-ts';
import {
  GRAPH_EDGE_SCHEMA_VERSION,
  GRAPH_NODE_SCHEMA_VERSION,
  GRAPH_SNAPSHOT_SCHEMA_VERSION,
} from '@aegis/contracts-ts';

export const TARGET_GRAPH_NODE_COUNT = 500 as const;
export const STRESS_GRAPH_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAW' as const;

function padId(index: number): string {
  return String(index).padStart(5, '0');
}

function buildClusters(nodes: GraphNodeV1[]): GraphClusterV1[] {
  const membersByCluster = new Map<string, string[]>();
  for (const node of nodes) {
    const clusterId = node.clusterId;
    if (!clusterId) {
      continue;
    }
    const members = membersByCluster.get(clusterId) ?? [];
    members.push(node.id);
    membersByCluster.set(clusterId, members);
  }

  return [...membersByCluster.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([id, memberNodeIds]) => ({
      schemaVersion: 1,
      id,
      label: `Cluster ${id.split(':').at(-1) ?? id}`,
      memberNodeIds,
      revision: 1,
    }));
}

export function buildTargetGraphSnapshot(
  runId = 'run_01ARZ3NDEKTSV4RRFFQ69G5FBX',
): GraphSnapshotV1 {
  const nodes: GraphNodeV1[] = [];
  const edges: GraphEdgeV1[] = [];
  const clusterCount = 12;

  for (let i = 0; i < TARGET_GRAPH_NODE_COUNT; i += 1) {
    const isHub = i % 25 === 0;
    nodes.push({
      schemaVersion: GRAPH_NODE_SCHEMA_VERSION,
      id: `asset:target-${padId(i)}`,
      entityType: 'asset',
      assetType: isHub ? 'service' : i % 2 === 0 ? 'device' : 'database',
      label: isHub ? `Hub ${String(i)}` : `Target Node ${String(i)}`,
      clusterId: `business-unit:cluster-${String(i % clusterCount).padStart(2, '0')}`,
      riskScore: (i % 100) / 100,
      criticality: ((i + 3) % 100) / 100,
      status: i % 23 === 0 ? 'suspicious' : 'normal',
      revision: 1,
    });
  }

  for (let i = 0; i < TARGET_GRAPH_NODE_COUNT; i += 1) {
    const hubIndex = Math.floor(i / 25) * 25;
    const chainTarget = i + 1 < TARGET_GRAPH_NODE_COUNT ? i + 1 : 0;
    const targets = [hubIndex, chainTarget, (i + 17) % TARGET_GRAPH_NODE_COUNT];

    for (const targetIndex of [...new Set(targets)]) {
      if (targetIndex === i) {
        continue;
      }
      edges.push({
        schemaVersion: GRAPH_EDGE_SCHEMA_VERSION,
        id: `edge:target-${padId(i)}-${padId(targetIndex)}`,
        source: `asset:target-${padId(i)}`,
        target: `asset:target-${padId(targetIndex)}`,
        relationshipType: targetIndex === hubIndex ? 'DEPENDS_ON' : 'COMMUNICATED_WITH',
        directed: true,
        confidence: 0.8,
        riskContribution: targetIndex === hubIndex ? 0.4 : 0.15,
        firstSeenAt: '2026-01-01T00:00:00.000Z',
        lastSeenAt: '2026-06-30T00:00:00.000Z',
        eventCount: i % 4,
        revision: 1,
      });
    }
  }

  return {
    schemaVersion: GRAPH_SNAPSHOT_SCHEMA_VERSION,
    runId,
    sequence: 2000,
    capturedAt: '2026-06-30T04:00:00.000Z',
    nodes,
    edges,
    clusters: buildClusters(nodes),
    revision: 1,
  };
}

export function buildStressGraphSnapshot(runId = STRESS_GRAPH_RUN_ID): GraphSnapshotV1 {
  const nodes: GraphNodeV1[] = [];
  const edges: GraphEdgeV1[] = [];
  const nodeCount = 2500;
  const clusterCount = 20;

  for (let i = 0; i < nodeCount; i += 1) {
    const isHub = i % 50 === 0;
    nodes.push({
      schemaVersion: GRAPH_NODE_SCHEMA_VERSION,
      id: `asset:stress-${padId(i)}`,
      entityType: 'asset',
      assetType: isHub ? 'service' : i % 3 === 0 ? 'device' : 'database',
      label: isHub ? `Stress Hub ${String(i)}` : `Stress Node ${String(i)}`,
      clusterId: `business-unit:cluster-${String(i % clusterCount).padStart(2, '0')}`,
      riskScore: (i % 100) / 100,
      criticality: ((i + 11) % 100) / 100,
      status: i % 19 === 0 ? 'suspicious' : 'normal',
      revision: 1,
    });
  }

  for (let i = 0; i < nodeCount; i += 1) {
    for (let j = 1; j <= 2; j += 1) {
      const targetIndex = (i + j * 41) % nodeCount;
      if (targetIndex === i) {
        continue;
      }
      edges.push({
        schemaVersion: GRAPH_EDGE_SCHEMA_VERSION,
        id: `edge:stress-${padId(i)}-${padId(targetIndex)}-${String(j)}`,
        source: `asset:stress-${padId(i)}`,
        target: `asset:stress-${padId(targetIndex)}`,
        relationshipType: j % 2 === 0 ? 'COMMUNICATED_WITH' : 'DEPENDS_ON',
        directed: true,
        confidence: 0.85,
        riskContribution: i % 50 === 0 ? 0.5 : 0.1,
        firstSeenAt: '2026-01-01T00:00:00.000Z',
        lastSeenAt: '2026-06-30T00:00:00.000Z',
        eventCount: i % 6,
        revision: 1,
      });
    }
  }

  return {
    schemaVersion: GRAPH_SNAPSHOT_SCHEMA_VERSION,
    runId,
    sequence: 3000,
    capturedAt: '2026-06-30T05:00:00.000Z',
    nodes,
    edges,
    clusters: buildClusters(nodes),
    revision: 1,
  };
}
