import type { GraphClusterV1, GraphNodeV1 } from '@aegis/contracts-ts';

import { computeInitialLayout } from '@/features/operational-graph/layout/initial-layout';

const MAX_SCENE_GROUND_SPAN = 720;

/**
 * §7.6 ground-plane mapping: the 2D layout lies flat on the scene's XZ ground
 * plane (scene X = layout X, scene Z = layout Y), staying synced to the
 * operational graph's authoritative placement. Scene Y (altitude) is left at
 * zero here — the semantic mapper derives it from risk score at render time,
 * so the skyline never feeds back into shared layout state.
 */
export function toScenePosition(xy: { x: number; y: number }): {
  x: number;
  y: number;
  z: number;
} {
  return {
    x: xy.x,
    y: 0,
    z: xy.y,
  };
}

export function resolveStablePositions(
  nodes: GraphNodeV1[],
  clusters: GraphClusterV1[],
  existingPositions: Record<string, { x: number; y: number }> = {},
  workerPositions: Record<string, { x: number; y: number }> = {},
): Record<string, { x: number; y: number; z: number }> {
  const layout2d = computeInitialLayout(nodes, clusters, {
    ...existingPositions,
    ...workerPositions,
  });
  const result: Record<string, { x: number; y: number; z: number }> = {};
  for (const node of nodes) {
    const xy = layout2d[node.id] ?? { x: 0, y: 0 };
    result[node.id] = toScenePosition(xy);
  }
  return result;
}

/**
 * Sigma normalizes arbitrary graph coordinates internally before drawing.
 * Three.js consumes world units directly, so its read-only projection needs
 * the equivalent bounded scale to keep node geometry legible. Only the ground
 * plane (X/Z) is normalized; altitude is derived later from risk score.
 */
export function normalizeScenePositions(
  positions: Record<string, { x: number; y: number; z: number }>,
): Record<string, { x: number; y: number; z: number }> {
  const entries = Object.entries(positions);
  if (entries.length === 0) {
    return {};
  }

  const xs = entries.map(([, position]) => position.x);
  const zs = entries.map(([, position]) => position.z);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);
  const centerX = (minX + maxX) / 2;
  const centerZ = (minZ + maxZ) / 2;
  const largestSpan = Math.max(maxX - minX, maxZ - minZ);
  const scale = largestSpan > MAX_SCENE_GROUND_SPAN ? MAX_SCENE_GROUND_SPAN / largestSpan : 1;

  return Object.fromEntries(
    entries.map(([nodeId, position]) => [
      nodeId,
      {
        x: (position.x - centerX) * scale,
        y: position.y,
        z: (position.z - centerZ) * scale,
      },
    ]),
  );
}
