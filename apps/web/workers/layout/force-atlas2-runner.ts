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

  resolveNodeOverlaps(graph, pinnedNodes);

  const positions: Record<string, { x: number; y: number }> = {};
  graph.forEachNode((nodeId, attributes) => {
    positions[nodeId] = {
      x: attributes.x as number,
      y: attributes.y as number,
    };
  });

  return { positions, iterationsCompleted };
}

const OVERLAP_RADIUS = 60;
const OVERLAP_SWEEPS = 32;

/**
 * Post-layout collision pass: FA2 without size awareness happily stacks nodes
 * on top of each other in dense clusters. A few relaxation sweeps pushing any
 * pair closer than 2×OVERLAP_RADIUS apart guarantees labels and hit targets
 * never fully overlap. Deterministic (fixed order, no randomness).
 */
function resolveNodeOverlaps(graph: Graph, pinnedNodes: ReadonlySet<string>): void {
  const nodeIds = graph.nodes().sort((a, b) => a.localeCompare(b));
  const minDistance = OVERLAP_RADIUS * 2;

  for (let sweep = 0; sweep < OVERLAP_SWEEPS; sweep += 1) {
    let moved = false;
    for (let i = 0; i < nodeIds.length; i += 1) {
      for (let j = i + 1; j < nodeIds.length; j += 1) {
        const a = nodeIds[i] as string;
        const b = nodeIds[j] as string;
        const ax = graph.getNodeAttribute(a, 'x') as number;
        const ay = graph.getNodeAttribute(a, 'y') as number;
        const bx = graph.getNodeAttribute(b, 'x') as number;
        const by = graph.getNodeAttribute(b, 'y') as number;
        let dx = bx - ax;
        let dy = by - ay;
        let distance = Math.hypot(dx, dy);
        if (distance >= minDistance) {
          continue;
        }
        if (distance < 1e-6) {
          // Coincident nodes: separate along a deterministic direction derived
          // from the pair's order so reruns stay reproducible.
          const angle = ((i * 31 + j) % 360) * (Math.PI / 180);
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }
        const push = (minDistance - distance) / 2;
        const ux = (dx / distance) * push;
        const uy = (dy / distance) * push;
        const aPinned = pinnedNodes.has(a);
        const bPinned = pinnedNodes.has(b);
        if (!aPinned) {
          graph.setNodeAttribute(a, 'x', ax - ux * (bPinned ? 2 : 1));
          graph.setNodeAttribute(a, 'y', ay - uy * (bPinned ? 2 : 1));
        }
        if (!bPinned) {
          graph.setNodeAttribute(b, 'x', bx + ux * (aPinned ? 2 : 1));
          graph.setNodeAttribute(b, 'y', by + uy * (aPinned ? 2 : 1));
        }
        moved = true;
      }
    }
    if (!moved) {
      break;
    }
  }
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
