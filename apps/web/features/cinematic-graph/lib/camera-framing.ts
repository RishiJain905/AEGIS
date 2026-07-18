import type { CameraBookmark3D, SceneNode } from '../contracts';
import { defaultCameraBookmark3D } from '../contracts/camera-bookmark-3d';

const MIN_SCENE_RADIUS = 80;
const CAMERA_PADDING = 1.2;
const CAMERA_DIRECTION = { x: 0.68, y: 0.52, z: 0.72 } as const;

type FrameableNode = Pick<SceneNode, 'position' | 'size'>;

function directionLength(): number {
  return Math.hypot(CAMERA_DIRECTION.x, CAMERA_DIRECTION.y, CAMERA_DIRECTION.z);
}

export function frameSceneNodes(
  nodes: readonly FrameableNode[],
  fov = defaultCameraBookmark3D.fov,
): CameraBookmark3D {
  if (nodes.length === 0) {
    return defaultCameraBookmark3D;
  }

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;

  for (const node of nodes) {
    const radius = Math.max(1, node.size);
    minX = Math.min(minX, node.position.x - radius);
    minY = Math.min(minY, node.position.y - radius);
    minZ = Math.min(minZ, node.position.z - radius);
    maxX = Math.max(maxX, node.position.x + radius);
    maxY = Math.max(maxY, node.position.y + radius);
    maxZ = Math.max(maxZ, node.position.z + radius);
  }

  const target = {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    z: (minZ + maxZ) / 2,
  };
  const radius = Math.max(
    MIN_SCENE_RADIUS,
    ...nodes.map((node) =>
      Math.hypot(
        node.position.x - target.x,
        node.position.y - target.y,
        node.position.z - target.z,
      ),
    ),
  );
  const halfFovRadians = (Math.max(20, Math.min(100, fov)) * Math.PI) / 360;
  const distance = (radius / Math.sin(halfFovRadians)) * CAMERA_PADDING;
  const normalizer = directionLength();

  return {
    schemaVersion: 1,
    position: {
      x: target.x + (CAMERA_DIRECTION.x / normalizer) * distance,
      y: target.y + (CAMERA_DIRECTION.y / normalizer) * distance,
      z: target.z + (CAMERA_DIRECTION.z / normalizer) * distance,
    },
    target,
    fov,
  };
}
