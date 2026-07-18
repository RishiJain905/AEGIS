import { describe, expect, it } from 'vitest';

import { defaultCameraBookmark3D } from '../contracts/camera-bookmark-3d';
import { focusNodeBookmark, frameSceneNodes } from './camera-framing';

function frameable(x: number, y: number, z: number, size = 12) {
  return { position: { x, y, z }, size };
}

describe('focusNodeBookmark', () => {
  const nodeOrigin = frameable(0, 0, 0);
  const nodeEast = frameable(300, 40, -60);
  const nodeWest = frameable(-280, -120, 90);
  const sceneNodes = [nodeOrigin, nodeEast, nodeWest, frameable(120, 260, 30)];

  it('targets the node exactly', () => {
    const bookmark = focusNodeBookmark(nodeEast, defaultCameraBookmark3D, sceneNodes);
    expect(bookmark.target).toEqual(nodeEast.position);
  });

  it('preserves the current view direction instead of flipping the camera', () => {
    const camera = frameSceneNodes(sceneNodes);
    const bookmark = focusNodeBookmark(nodeWest, camera, sceneNodes);

    const currentDir = {
      x: camera.position.x - camera.target.x,
      y: camera.position.y - camera.target.y,
      z: camera.position.z - camera.target.z,
    };
    const focusDir = {
      x: bookmark.position.x - bookmark.target.x,
      y: bookmark.position.y - bookmark.target.y,
      z: bookmark.position.z - bookmark.target.z,
    };
    const dot = currentDir.x * focusDir.x + currentDir.y * focusDir.y + currentDir.z * focusDir.z;
    const cosine =
      dot /
      (Math.hypot(currentDir.x, currentDir.y, currentDir.z) *
        Math.hypot(focusDir.x, focusDir.y, focusDir.z));
    expect(cosine).toBeCloseTo(1, 5);
  });

  it('keeps enough distance that the rest of the scene stays in view', () => {
    const camera = frameSceneNodes(sceneNodes);
    const focused = nodeOrigin;
    const bookmark = focusNodeBookmark(focused, camera, sceneNodes);

    const distance = Math.hypot(
      bookmark.position.x - focused.position.x,
      bookmark.position.y - focused.position.y,
      bookmark.position.z - focused.position.z,
    );
    const farthestNode = Math.max(
      ...sceneNodes.map((node) =>
        Math.hypot(
          node.position.x - focused.position.x,
          node.position.y - focused.position.y,
          node.position.z - focused.position.z,
        ),
      ),
    );
    expect(distance).toBeGreaterThanOrEqual(farthestNode);
    expect(distance).toBeGreaterThanOrEqual(240);
    expect(distance).toBeLessThanOrEqual(2_400);
  });

  it('falls back to the canonical direction for a degenerate camera', () => {
    const degenerate = {
      ...defaultCameraBookmark3D,
      position: { x: 5, y: 5, z: 5 },
      target: { x: 5, y: 5, z: 5 },
    };
    const bookmark = focusNodeBookmark(nodeOrigin, degenerate, sceneNodes);
    expect(Number.isFinite(bookmark.position.x)).toBe(true);
    expect(Number.isFinite(bookmark.position.y)).toBe(true);
    expect(Number.isFinite(bookmark.position.z)).toBe(true);
    expect(bookmark.position).not.toEqual(bookmark.target);
  });
});
