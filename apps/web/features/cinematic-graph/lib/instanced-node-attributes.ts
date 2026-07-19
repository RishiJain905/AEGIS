import * as THREE from 'three';

import type { SceneNode } from '../contracts';
import { resolveThreeColor } from './three-color';

export function nodeRadius(node: SceneNode): number {
  return Math.max(9, node.size * 1.05) * node.sizeTier * (node.selected ? 1.12 : 1);
}

// Module-level scratch objects: this runs on node-set changes (not per frame),
// but stays allocation-free for everything except the emissive upload buffer.
const scratchObject = new THREE.Object3D();
const scratchColor = new THREE.Color();

/**
 * Uploads the per-instance presentation state (§7.1–§7.3) for the instanced
 * node mesh and its additive color coat: transform, base color, emissive
 * accent, and — critically — the refreshed instanced bounding spheres.
 *
 * three caches an InstancedMesh-level bounding sphere the first time the
 * frustum check or raycaster needs one. On a warm remount (cross-run
 * navigation) the render loop is already hot, so that first frame can happen
 * while every instance matrix is still identity — caching a unit sphere at
 * the origin. `instanceMatrix.needsUpdate` does NOT invalidate that cache, so
 * without the explicit recompute below every later raycast tests the stale
 * sphere and misses: hover/click go permanently dead until a hard reload.
 */
export function applyInstancedNodeAttributes(
  mesh: THREE.InstancedMesh,
  colorCoat: THREE.InstancedMesh | null,
  nodes: SceneNode[],
): void {
  const emissiveArray = new Float32Array(Math.max(nodes.length, 1) * 3);

  nodes.forEach((node, index) => {
    const radius = nodeRadius(node);
    scratchObject.position.set(node.position.x, node.position.y, node.position.z);
    scratchObject.scale.setScalar(node.dimmed ? radius * 0.72 : radius);
    scratchObject.updateMatrix();
    mesh.setMatrixAt(index, scratchObject.matrix);

    scratchColor.copy(resolveThreeColor(node.color).color);
    if (node.dimmed) {
      scratchColor.multiplyScalar(0.28);
    } else if (node.highlighted || node.selected) {
      scratchColor.offsetHSL(0, 0.08, 0.08);
    }
    mesh.setColorAt(index, scratchColor);

    // §7.1: risk/status accent as an emissive tint (status wins over risk;
    // quiet neutral otherwise), resolved upstream in the scene adapter.
    const accent = resolveThreeColor(node.emissiveColor).color;
    const emissiveScale = node.dimmed ? 0.12 : node.selected || node.highlighted ? 0.85 : 0.62;
    emissiveArray[index * 3] = accent.r * emissiveScale;
    emissiveArray[index * 3 + 1] = accent.g * emissiveScale;
    emissiveArray[index * 3 + 2] = accent.b * emissiveScale;

    if (colorCoat) {
      scratchObject.scale.setScalar((node.dimmed ? radius * 0.72 : radius) * 1.012);
      scratchObject.updateMatrix();
      colorCoat.setMatrixAt(index, scratchObject.matrix);
      // The additive coat carries the same accent so node + glow read as one
      // coherent risk/status signal (§7.3).
      scratchColor.copy(accent).multiplyScalar(node.dimmed ? 0.1 : 1);
      colorCoat.setColorAt(index, scratchColor);
    }
  });

  mesh.geometry.setAttribute(
    'instanceEmissive',
    new THREE.InstancedBufferAttribute(emissiveArray, 3),
  );
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) {
    mesh.instanceColor.needsUpdate = true;
  }
  mesh.computeBoundingSphere();
  if (colorCoat) {
    colorCoat.instanceMatrix.needsUpdate = true;
    if (colorCoat.instanceColor) {
      colorCoat.instanceColor.needsUpdate = true;
    }
    colorCoat.computeBoundingSphere();
  }
}
