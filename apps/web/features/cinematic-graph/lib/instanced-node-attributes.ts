import * as THREE from 'three';

import type { SceneNode } from '../contracts';
import { resolveThreeColor } from './three-color';

export function nodeRadius(node: SceneNode): number {
  return Math.max(9, node.size * 1.05) * node.sizeTier * (node.selected ? 1.12 : 1);
}

/** Cold husk tint for fog-of-war (undisclosed) assets. */
const FOG_HUSK = new THREE.Color('#232c3d');
/** Desaturation target for contained (severed) assets. */
const CONTAINED_TINT = new THREE.Color('#7a86ad');

// Module-level scratch objects: this runs on node-set changes (not per frame),
// but stays allocation-free for everything except the emissive upload buffer.
const scratchObject = new THREE.Object3D();
const scratchColor = new THREE.Color();

/**
 * Uploads the per-instance presentation state for one typed instanced node
 * mesh: transform, base color, emissive accent, and — critically — the
 * refreshed instanced bounding spheres.
 *
 * Fog of war and containment are baked here: undisclosed nodes collapse to a
 * dark husk with almost no emissive; contained nodes desaturate toward a cold
 * violet so a severed asset visibly drops out of the fight.
 *
 * three caches an InstancedMesh-level bounding sphere the first time the
 * frustum check or raycaster needs one. On a warm remount (cross-run
 * navigation) the render loop is already hot, so that first frame can happen
 * while every instance matrix is still identity — caching a unit sphere at
 * the origin. `instanceMatrix.needsUpdate` does NOT invalidate that cache, so
 * without the explicit recompute below every later raycast tests the stale
 * sphere and misses: hover/click go permanently dead until a hard reload.
 */
export function applyInstancedNodeAttributes(mesh: THREE.InstancedMesh, nodes: SceneNode[]): void {
  const emissiveArray = new Float32Array(Math.max(nodes.length, 1) * 3);

  nodes.forEach((node, index) => {
    const radius = nodeRadius(node);
    const scale = node.dimmed ? radius * 0.72 : node.disclosed ? radius : radius * 0.88;
    scratchObject.position.set(node.position.x, node.position.y, node.position.z);
    scratchObject.scale.setScalar(scale);
    scratchObject.updateMatrix();
    mesh.setMatrixAt(index, scratchObject.matrix);

    scratchColor.copy(resolveThreeColor(node.color).color);
    if (!node.disclosed) {
      scratchColor.lerp(FOG_HUSK, 0.82);
    } else if (node.status === 'contained') {
      scratchColor.lerp(CONTAINED_TINT, 0.55);
    }
    if (node.dimmed) {
      scratchColor.multiplyScalar(0.28);
    } else if (node.highlighted || node.selected) {
      scratchColor.offsetHSL(0, 0.08, 0.08);
    }
    mesh.setColorAt(index, scratchColor);

    // Risk/status accent as an emissive tint (status wins over risk; quiet
    // neutral otherwise), resolved upstream in the scene adapter. Undisclosed
    // assets barely glow — detection is what lights them up.
    const accent = resolveThreeColor(node.emissiveColor).color;
    const emissiveScale = !node.disclosed
      ? 0.06
      : node.dimmed
        ? 0.12
        : node.selected || node.highlighted
          ? 0.85
          : 0.62;
    emissiveArray[index * 3] = accent.r * emissiveScale;
    emissiveArray[index * 3 + 1] = accent.g * emissiveScale;
    emissiveArray[index * 3 + 2] = accent.b * emissiveScale;
  });

  mesh.geometry.setAttribute(
    'instanceEmissive',
    new THREE.InstancedBufferAttribute(emissiveArray, 3),
  );
  mesh.count = nodes.length;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) {
    mesh.instanceColor.needsUpdate = true;
  }
  mesh.computeBoundingSphere();
}

/** Platform surface height the pylons rise from. */
const PYLON_BASE_Y = 1.5;

/**
 * Anchors every node to its platform with a thin light pylon: an instanced
 * unit box scaled from the platform surface up to just below the node body.
 * Pylon color follows the node's emissive accent so a compromised asset's
 * whole column burns red, while fog-of-war assets keep a barely-there stem.
 */
export function applyPylonAttributes(mesh: THREE.InstancedMesh, nodes: SceneNode[]): void {
  nodes.forEach((node, index) => {
    const radius = nodeRadius(node);
    const top = Math.max(PYLON_BASE_Y + 2, node.position.y - radius * 0.6);
    const height = top - PYLON_BASE_Y;
    scratchObject.position.set(node.position.x, PYLON_BASE_Y + height / 2, node.position.z);
    scratchObject.scale.set(0.8, height, 0.8);
    scratchObject.updateMatrix();
    mesh.setMatrixAt(index, scratchObject.matrix);

    if (!node.disclosed) {
      scratchColor.set('#131a26');
    } else if (node.status === 'compromised') {
      scratchColor.copy(resolveThreeColor(node.emissiveColor).color);
    } else {
      scratchColor.copy(resolveThreeColor(node.emissiveColor).color).multiplyScalar(0.42);
    }
    if (node.dimmed) {
      scratchColor.multiplyScalar(0.25);
    }
    mesh.setColorAt(index, scratchColor);
  });

  mesh.count = nodes.length;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) {
    mesh.instanceColor.needsUpdate = true;
  }
  mesh.computeBoundingSphere();
}
