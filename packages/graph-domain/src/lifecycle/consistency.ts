import type { GraphClusterV1 } from '@aegis/contracts-ts';

import {
  EDGE_ATTR_KEY,
  getNodeCanonical,
  type CanonicalGraph,
} from '../adapters/canonical-graphology';
import type { GraphConsistencyIssue, GraphConsistencyReport } from '../contracts/types';

export function validateGraphConsistency(
  graph: CanonicalGraph,
  clusters: Map<string, GraphClusterV1>,
): GraphConsistencyReport {
  const issues: GraphConsistencyIssue[] = [];
  const nodeIds = new Set<string>();
  graph.forEachNode((nodeId) => {
    nodeIds.add(nodeId);
  });

  graph.forEachEdge((edgeId, edgeAttributes, source, target) => {
    const edge = edgeAttributes[EDGE_ATTR_KEY];
    if (!nodeIds.has(source)) {
      issues.push({
        code: 'ORPHAN_EDGE_SOURCE',
        message: `Edge ${edgeId} references missing source ${source}`,
        entityId: edgeId,
        details: { source, target },
      });
    }
    if (!nodeIds.has(target)) {
      issues.push({
        code: 'ORPHAN_EDGE_TARGET',
        message: `Edge ${edgeId} references missing target ${target}`,
        entityId: edgeId,
        details: { source, target },
      });
    }
    if (edge.source !== source || edge.target !== target) {
      issues.push({
        code: 'EDGE_ENDPOINT_MISMATCH',
        message: `Edge ${edgeId} canonical endpoints do not match graph topology`,
        entityId: edgeId,
        details: { canonicalSource: edge.source, canonicalTarget: edge.target, source, target },
      });
    }
  });

  for (const cluster of clusters.values()) {
    for (const memberId of cluster.memberNodeIds) {
      if (!nodeIds.has(memberId)) {
        issues.push({
          code: 'CLUSTER_MEMBER_MISSING',
          message: `Cluster ${cluster.id} references missing member ${memberId}`,
          entityId: cluster.id,
          details: { memberId },
        });
      }
    }
  }

  for (const nodeId of nodeIds) {
    const node = getNodeCanonical(graph, nodeId);
    if (node === undefined) {
      issues.push({
        code: 'MISSING_NODE_CANONICAL',
        message: `Node ${nodeId} has no canonical attributes`,
        entityId: nodeId,
      });
      continue;
    }
    if (node.clusterId !== undefined) {
      const clusterHasMember = [...clusters.values()].some(
        (cluster) => cluster.id === node.clusterId || cluster.memberNodeIds.includes(nodeId),
      );
      if (!clusterHasMember) {
        issues.push({
          code: 'UNRESOLVED_CLUSTER_REFERENCE',
          message: `Node ${nodeId} references cluster ${node.clusterId} that is not defined`,
          entityId: nodeId,
          details: { clusterId: node.clusterId },
        });
      }
    }
  }

  return {
    valid: issues.length === 0,
    issues,
    nodeCount: graph.order,
    edgeCount: graph.size,
    clusterCount: clusters.size,
  };
}
