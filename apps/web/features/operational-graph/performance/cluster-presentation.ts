import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

export interface ClusterPresentationNode {
  id: string;
  clusterId: string;
  label: string;
  memberIds: string[];
  memberCount: number;
}

export function buildClusterPresentationNodes(
  nodes: GraphNodeV1[],
  clusters: GraphClusterV1[],
  collapsedClusterIds: string[],
): {
  presentationNodes: ClusterPresentationNode[];
  hiddenNodeIds: Set<string>;
} {
  const hiddenNodeIds = new Set<string>();
  const presentationNodes: ClusterPresentationNode[] = [];
  const collapsed = new Set(collapsedClusterIds);

  const nodesByCluster = new Map<string, GraphNodeV1[]>();
  for (const node of nodes) {
    const clusterId = node.clusterId ?? 'unclustered';
    const group = nodesByCluster.get(clusterId) ?? [];
    group.push(node);
    nodesByCluster.set(clusterId, group);
  }

  for (const clusterId of collapsed) {
    const members = nodesByCluster.get(clusterId) ?? [];
    if (members.length === 0) {
      continue;
    }

    const clusterMeta = clusters.find((cluster) => cluster.id === clusterId);
    for (const member of members) {
      hiddenNodeIds.add(member.id);
    }

    presentationNodes.push({
      id: `presentation:cluster:${clusterId}`,
      clusterId,
      label: clusterMeta?.label ?? `Cluster ${clusterId}`,
      memberIds: members.map((member) => member.id),
      memberCount: members.length,
    });
  }

  return { presentationNodes, hiddenNodeIds };
}

export function toggleCollapsedCluster(collapsedClusterIds: string[], clusterId: string): string[] {
  if (collapsedClusterIds.includes(clusterId)) {
    return collapsedClusterIds.filter((id) => id !== clusterId);
  }
  return [...collapsedClusterIds, clusterId];
}

export function autoCollapseClusterIds(nodes: GraphNodeV1[], threshold: number): string[] {
  if (!Number.isFinite(threshold)) {
    return [];
  }

  const counts = new Map<string, number>();
  for (const node of nodes) {
    const clusterId = node.clusterId;
    if (!clusterId) {
      continue;
    }
    counts.set(clusterId, (counts.get(clusterId) ?? 0) + 1);
  }

  return [...counts.entries()]
    .filter(([, count]) => count >= threshold)
    .map(([clusterId]) => clusterId)
    .sort();
}
