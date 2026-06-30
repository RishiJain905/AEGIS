import Graph from 'graphology';
import type { Attributes } from 'graphology-types';
import type {
  GraphClusterV1,
  GraphEdgeV1,
  GraphNodeV1,
  GraphSnapshotV1,
} from '@aegis/contracts-ts';
import { GRAPH_SNAPSHOT_SCHEMA_VERSION } from '@aegis/contracts-ts';

export const NODE_ATTR_KEY = 'canonical' as const;
export const EDGE_ATTR_KEY = 'canonical' as const;

export interface CanonicalNodeAttributes extends Attributes {
  [NODE_ATTR_KEY]: GraphNodeV1;
}

export interface CanonicalEdgeAttributes extends Attributes {
  [EDGE_ATTR_KEY]: GraphEdgeV1;
}

export type CanonicalGraph = Graph<CanonicalNodeAttributes, CanonicalEdgeAttributes>;

export function createEmptyGraph(): CanonicalGraph {
  return new Graph<CanonicalNodeAttributes, CanonicalEdgeAttributes>({
    multi: false,
    type: 'mixed',
    allowSelfLoops: false,
  });
}

export function loadSnapshotIntoGraph(
  graph: CanonicalGraph,
  snapshot: GraphSnapshotV1,
): Map<string, GraphClusterV1> {
  graph.clear();

  for (const node of snapshot.nodes) {
    graph.addNode(node.id, { [NODE_ATTR_KEY]: node });
  }

  for (const edge of snapshot.edges) {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
      continue;
    }
    if (graph.hasEdge(edge.id)) {
      graph.dropEdge(edge.id);
    }
    graph.addEdgeWithKey(edge.id, edge.source, edge.target, { [EDGE_ATTR_KEY]: edge });
  }

  const clusters = new Map<string, GraphClusterV1>();
  for (const cluster of snapshot.clusters) {
    clusters.set(cluster.id, cluster);
  }

  return clusters;
}

export function exportGraphToSnapshot(
  graph: CanonicalGraph,
  clusters: Map<string, GraphClusterV1>,
  metadata: {
    runId: string;
    sequence: number;
    capturedAt: string;
    revision: number;
  },
): GraphSnapshotV1 {
  const nodes: GraphNodeV1[] = [];
  graph.forEachNode((nodeId, attributes) => {
    nodes.push(attributes[NODE_ATTR_KEY]);
    void nodeId;
  });
  nodes.sort((a, b) => a.id.localeCompare(b.id));

  const edges: GraphEdgeV1[] = [];
  graph.forEachEdge((_edgeId, attributes) => {
    edges.push(attributes[EDGE_ATTR_KEY]);
  });
  edges.sort((a, b) => a.id.localeCompare(b.id));

  const clusterList = [...clusters.values()].sort((a, b) => a.id.localeCompare(b.id));

  return {
    schemaVersion: GRAPH_SNAPSHOT_SCHEMA_VERSION,
    runId: metadata.runId,
    sequence: metadata.sequence,
    capturedAt: metadata.capturedAt,
    nodes,
    edges,
    clusters: clusterList,
    revision: metadata.revision,
  };
}

export function getNodeCanonical(graph: CanonicalGraph, nodeId: string): GraphNodeV1 | undefined {
  if (!graph.hasNode(nodeId)) {
    return undefined;
  }
  return graph.getNodeAttributes(nodeId)[NODE_ATTR_KEY];
}

export function getEdgeCanonical(graph: CanonicalGraph, edgeId: string): GraphEdgeV1 | undefined {
  if (!graph.hasEdge(edgeId)) {
    return undefined;
  }
  return graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
}
