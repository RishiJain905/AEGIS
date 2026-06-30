import type { GraphClusterV1 } from '@aegis/contracts-ts';

import { EDGE_ATTR_KEY, type CanonicalGraph } from '../adapters/canonical-graphology';
import type {
  IncidentSubgraphOptions,
  IncidentSubgraphResult,
  NeighborhoodOptions,
  NeighborhoodResult,
} from '../contracts/types';
import { GraphDomainError, GraphDomainErrorCode } from '../errors/graph-domain-error';

function edgePassesFilter(
  relationshipType: string,
  directed: boolean,
  relationshipTypes: string[] | undefined,
  directedOnly: boolean | undefined,
): boolean {
  if (relationshipTypes !== undefined && relationshipTypes.length > 0) {
    if (!relationshipTypes.includes(relationshipType)) {
      return false;
    }
  }
  if (directedOnly === true && !directed) {
    return false;
  }
  return true;
}

export function getNeighborhoodOnGraph(
  graph: CanonicalGraph,
  nodeId: string,
  options: NeighborhoodOptions,
): NeighborhoodResult {
  if (!graph.hasNode(nodeId)) {
    throw new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_ENTITY_NOT_FOUND,
      message: `Node ${nodeId} not found`,
      details: { nodeId },
    });
  }

  const { hops, relationshipTypes, directedOnly, includeCenter = true } = options;
  const hopRings: string[][] = [];
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  if (includeCenter) {
    nodeIds.add(nodeId);
  }

  let frontier = new Set([nodeId]);
  const visited = new Set([nodeId]);

  for (let hop = 1; hop <= hops; hop += 1) {
    const ring: string[] = [];
    const nextFrontier = new Set<string>();

    for (const current of frontier) {
      const outbound = graph.outboundEdges(current);
      for (const edgeId of outbound) {
        const edge = graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
        if (
          !edgePassesFilter(edge.relationshipType, edge.directed, relationshipTypes, directedOnly)
        ) {
          continue;
        }
        const target = graph.target(edgeId);
        edgeIds.add(edgeId);
        if (!visited.has(target)) {
          visited.add(target);
          nodeIds.add(target);
          ring.push(target);
          nextFrontier.add(target);
        }
      }

      if (directedOnly !== true) {
        const inbound = graph.inboundEdges(current);
        for (const edgeId of inbound) {
          const edge = graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
          if (
            !edgePassesFilter(edge.relationshipType, edge.directed, relationshipTypes, directedOnly)
          ) {
            continue;
          }
          const source = graph.source(edgeId);
          edgeIds.add(edgeId);
          if (!visited.has(source)) {
            visited.add(source);
            nodeIds.add(source);
            ring.push(source);
            nextFrontier.add(source);
          }
        }
      }
    }

    ring.sort((a, b) => a.localeCompare(b));
    hopRings.push(ring);
    frontier = nextFrontier;
  }

  return {
    centerNodeId: nodeId,
    hops,
    nodeIds: [...nodeIds].sort((a, b) => a.localeCompare(b)),
    edgeIds: [...edgeIds].sort((a, b) => a.localeCompare(b)),
    hopRings,
    explanation: {
      nodesReached: nodeIds.size,
      edgesIncluded: edgeIds.size,
      relationshipTypes: relationshipTypes ?? [],
      directedOnly: directedOnly ?? false,
    },
  };
}

export function getIncidentSubgraphOnGraph(
  graph: CanonicalGraph,
  seedNodeIds: string[],
  options: IncidentSubgraphOptions = {},
): IncidentSubgraphResult {
  const hops = options.hops ?? 2;
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();
  const boundaryEdgeIds = new Set<string>();

  for (const seedId of seedNodeIds) {
    if (!graph.hasNode(seedId)) {
      continue;
    }
    const neighborhood = getNeighborhoodOnGraph(graph, seedId, {
      hops,
      relationshipTypes: options.relationshipTypes,
      directedOnly: options.directedOnly,
      includeCenter: true,
    });
    for (const id of neighborhood.nodeIds) {
      nodeIds.add(id);
    }
    for (const id of neighborhood.edgeIds) {
      edgeIds.add(id);
    }
  }

  for (const edgeId of edgeIds) {
    const source = graph.source(edgeId);
    const target = graph.target(edgeId);
    if (!nodeIds.has(source) || !nodeIds.has(target)) {
      boundaryEdgeIds.add(edgeId);
    }
  }

  return {
    seedNodeIds: [...seedNodeIds],
    nodeIds: [...nodeIds].sort((a, b) => a.localeCompare(b)),
    edgeIds: [...edgeIds].sort((a, b) => a.localeCompare(b)),
    boundaryEdgeIds: [...boundaryEdgeIds].sort((a, b) => a.localeCompare(b)),
    explanation: {
      hops,
      seedCount: seedNodeIds.length,
      inducedNodeCount: nodeIds.size,
      inducedEdgeCount: edgeIds.size,
    },
  };
}

export function getConnectedComponentsOnGraph(graph: CanonicalGraph): string[][] {
  const visited = new Set<string>();
  const components: string[][] = [];

  graph.forEachNode((nodeId) => {
    if (visited.has(nodeId)) {
      return;
    }

    const component: string[] = [];
    const queue = [nodeId];
    visited.add(nodeId);

    while (queue.length > 0) {
      const current = queue.shift();
      if (current === undefined) {
        break;
      }
      component.push(current);

      graph.forEachNeighbor(current, (neighbor) => {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      });
    }

    component.sort((a, b) => a.localeCompare(b));
    components.push(component);
  });

  components.sort((a, b) => (a[0] ?? '').localeCompare(b[0] ?? ''));
  return components;
}

export function getClusterMembersFromMap(
  clusters: Map<string, GraphClusterV1>,
  clusterId: string,
): string[] {
  const cluster = clusters.get(clusterId);
  if (cluster === undefined) {
    return [];
  }
  return [...cluster.memberNodeIds].sort((a, b) => a.localeCompare(b));
}

export function getDependenciesOnGraph(
  graph: CanonicalGraph,
  nodeId: string,
  maxDepth = 8,
): string[] {
  if (!graph.hasNode(nodeId)) {
    throw new GraphDomainError({
      code: GraphDomainErrorCode.GRAPH_ENTITY_NOT_FOUND,
      message: `Node ${nodeId} not found`,
      details: { nodeId },
    });
  }

  const dependencies = new Set<string>();
  const queue: Array<{ id: string; depth: number }> = [{ id: nodeId, depth: 0 }];
  const visited = new Set<string>([nodeId]);

  while (queue.length > 0) {
    const current = queue.shift();
    if (current === undefined) {
      break;
    }

    if (current.depth >= maxDepth) {
      continue;
    }

    const outbound = graph.outboundEdges(current.id);
    for (const edgeId of outbound) {
      const edge = graph.getEdgeAttributes(edgeId)[EDGE_ATTR_KEY];
      if (edge.relationshipType !== 'DEPENDS_ON') {
        continue;
      }
      const target = graph.target(edgeId);
      dependencies.add(target);
      if (!visited.has(target)) {
        visited.add(target);
        queue.push({ id: target, depth: current.depth + 1 });
      }
    }
  }

  dependencies.delete(nodeId);
  return [...dependencies].sort((a, b) => a.localeCompare(b));
}
