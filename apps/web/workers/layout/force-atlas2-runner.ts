import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';

import {
  LayoutWorkerErrorCode,
  LayoutWorkerResultStatus,
  type LayoutWorkerRequest,
} from '@/features/operational-graph/contracts/layout-worker-protocol';

export interface ForceAtlas2RunResult {
  positions: Record<string, { x: number; y: number }>;
  iterationsCompleted: number;
}

export function buildLayoutGraph(request: LayoutWorkerRequest): Graph {
  const graph = new Graph({ multi: false, type: 'undirected' });

  for (const node of request.nodes) {
    const seed = request.seedPositions[node.id];
    const x = node.pinned && node.x !== undefined ? node.x : (seed?.x ?? node.x ?? 0);
    const y = node.pinned && node.y !== undefined ? node.y : (seed?.y ?? node.y ?? 0);
    graph.addNode(node.id, { x, y, pinned: node.pinned });
  }

  for (const edge of request.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target) && edge.source !== edge.target) {
      if (!graph.hasEdge(edge.source, edge.target)) {
        graph.addEdge(edge.source, edge.target, { weight: edge.weight });
      }
    }
  }

  return graph;
}

export function runForceAtlas2(
  request: LayoutWorkerRequest,
  shouldCancel: () => boolean,
  onProgress?: (iterationsCompleted: number) => void,
): ForceAtlas2RunResult {
  const graph = buildLayoutGraph(request);
  const pinnedNodes = new Set(request.nodes.filter((node) => node.pinned).map((node) => node.id));
  const settings = {
    iterations: request.settings.iterations,
    settings: {
      gravity: request.settings.gravity,
      scalingRatio: request.settings.scalingRatio,
      barnesHutOptimize: request.settings.barnesHutOptimize,
      slowDown: request.settings.slowDown,
    },
  };

  let iterationsCompleted = 0;
  const batchSize = Math.max(1, Math.floor(request.settings.iterations / 10));

  while (iterationsCompleted < request.settings.iterations) {
    if (shouldCancel()) {
      break;
    }

    const remaining = request.settings.iterations - iterationsCompleted;
    const currentBatch = Math.min(batchSize, remaining);

    forceAtlas2.assign(graph, {
      iterations: currentBatch,
      settings: settings.settings,
    });

    for (const nodeId of pinnedNodes) {
      const node = request.nodes.find((item) => item.id === nodeId);
      if (!node || node.x === undefined || node.y === undefined) {
        continue;
      }
      graph.setNodeAttribute(nodeId, 'x', node.x);
      graph.setNodeAttribute(nodeId, 'y', node.y);
    }

    iterationsCompleted += currentBatch;
    onProgress?.(iterationsCompleted);
  }

  const positions: Record<string, { x: number; y: number }> = {};
  graph.forEachNode((nodeId, attributes) => {
    positions[nodeId] = {
      x: attributes.x as number,
      y: attributes.y as number,
    };
  });

  return { positions, iterationsCompleted };
}

export function createCancelledResult(
  request: LayoutWorkerRequest,
  iterationsCompleted: number,
  durationMs: number,
) {
  return {
    protocolVersion: 1 as const,
    requestId: request.requestId,
    graphRevision: request.graphRevision,
    status: LayoutWorkerResultStatus.CANCELLED,
    iterationsCompleted,
    durationMs,
    errorCode: LayoutWorkerErrorCode.CANCELLED,
    errorMessage: 'Layout cancelled',
  };
}

export function createCompleteResult(
  request: LayoutWorkerRequest,
  positions: Record<string, { x: number; y: number }>,
  iterationsCompleted: number,
  durationMs: number,
) {
  return {
    protocolVersion: 1 as const,
    requestId: request.requestId,
    graphRevision: request.graphRevision,
    status: LayoutWorkerResultStatus.COMPLETE,
    positions,
    iterationsCompleted,
    durationMs,
  };
}
