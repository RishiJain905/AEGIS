import type { GraphPathQueryV1, GraphPathResultV1 } from '@aegis/contracts-ts';
import { GRAPH_PATH_RESULT_SCHEMA_VERSION, RelationshipType } from '@aegis/contracts-ts';

import { EDGE_ATTR_KEY, type CanonicalGraph } from '../adapters/canonical-graphology';

function edgeMatchesFilter(
  relationshipType: string,
  directed: boolean,
  relationshipTypes: string[],
  directedOnly: boolean,
): boolean {
  if (relationshipTypes.length > 0 && !relationshipTypes.includes(relationshipType)) {
    return false;
  }
  if (directedOnly && !directed) {
    return false;
  }
  return true;
}

function comparePaths(a: string[], b: string[]): number {
  const maxLen = Math.max(a.length, b.length);
  for (let i = 0; i < maxLen; i += 1) {
    const aVal = a[i] ?? '';
    const bVal = b[i] ?? '';
    const cmp = aVal.localeCompare(bVal);
    if (cmp !== 0) {
      return cmp;
    }
  }
  return 0;
}

export function queryPathsOnGraph(
  graph: CanonicalGraph,
  query: GraphPathQueryV1,
): GraphPathResultV1 {
  const { sourceId, targetId, maxHops, relationshipTypes, directedOnly } = query;

  if (!graph.hasNode(sourceId) || !graph.hasNode(targetId)) {
    return {
      schemaVersion: GRAPH_PATH_RESULT_SCHEMA_VERSION,
      runId: query.runId,
      sourceId,
      targetId,
      paths: [],
      explanation: {
        hopCount: 0,
        pathsConsidered: 0,
        reason: 'source_or_target_not_found',
      },
    };
  }

  if (sourceId === targetId) {
    return {
      schemaVersion: GRAPH_PATH_RESULT_SCHEMA_VERSION,
      runId: query.runId,
      sourceId,
      targetId,
      paths: [[sourceId]],
      explanation: { hopCount: 0, pathsConsidered: 1, relationshipTypes },
    };
  }

  const paths: string[][] = [];
  let pathsConsidered = 0;

  const queue: Array<{ path: string[]; visited: Set<string> }> = [
    { path: [sourceId], visited: new Set([sourceId]) },
  ];

  while (queue.length > 0) {
    const current = queue.shift();
    if (current === undefined) {
      break;
    }

    const { path, visited } = current;
    const lastNode = path[path.length - 1];
    if (lastNode === undefined) {
      continue;
    }

    if (path.length - 1 >= maxHops) {
      continue;
    }

    const neighbors = graph.outboundEdges(lastNode);
    for (const edgeId of neighbors) {
      const edgeAttrs = graph.getEdgeAttributes(edgeId);
      const edge = edgeAttrs[EDGE_ATTR_KEY];
      pathsConsidered += 1;

      if (
        !edgeMatchesFilter(edge.relationshipType, edge.directed, relationshipTypes, directedOnly)
      ) {
        continue;
      }

      const nextNode = graph.target(edgeId);
      const nextPath = [...path, nextNode];

      if (nextNode === targetId) {
        paths.push(nextPath);
        continue;
      }

      if (!visited.has(nextNode) && nextPath.length <= maxHops) {
        const nextVisited = new Set(visited);
        nextVisited.add(nextNode);
        queue.push({ path: nextPath, visited: nextVisited });
      }
    }

    if (!directedOnly) {
      const inbound = graph.inboundEdges(lastNode);
      for (const edgeId of inbound) {
        const edgeAttrs = graph.getEdgeAttributes(edgeId);
        const edge = edgeAttrs[EDGE_ATTR_KEY];
        pathsConsidered += 1;

        if (
          !edgeMatchesFilter(edge.relationshipType, edge.directed, relationshipTypes, directedOnly)
        ) {
          continue;
        }

        const nextNode = graph.source(edgeId);
        if (visited.has(nextNode)) {
          continue;
        }

        const nextPath = [...path, nextNode];
        if (nextNode === targetId) {
          paths.push(nextPath);
          continue;
        }

        if (nextPath.length <= maxHops) {
          const nextVisited = new Set(visited);
          nextVisited.add(nextNode);
          queue.push({ path: nextPath, visited: nextVisited });
        }
      }
    }
  }

  paths.sort(comparePaths);

  const shortestHopCount = paths.length > 0 ? (paths[0]?.length ?? 1) - 1 : 0;

  return {
    schemaVersion: GRAPH_PATH_RESULT_SCHEMA_VERSION,
    runId: query.runId,
    sourceId,
    targetId,
    paths,
    explanation: {
      hopCount: shortestHopCount,
      pathsConsidered,
      pathsFound: paths.length,
      relationshipTypes:
        relationshipTypes.length > 0 ? relationshipTypes : Object.values(RelationshipType),
      directedOnly,
      ordering: 'lexicographic_by_node_id',
    },
  };
}
