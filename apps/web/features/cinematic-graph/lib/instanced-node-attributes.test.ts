import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import type { SceneNode } from '../contracts';
import { SCENE_NODE_SCHEMA_VERSION } from '../contracts';
import { applyInstancedNodeAttributes } from './instanced-node-attributes';
import { resolveThreeColor } from './three-color';

function makeSceneNode(overrides: Partial<SceneNode> = {}): SceneNode {
  return {
    schemaVersion: SCENE_NODE_SCHEMA_VERSION,
    id: 'asset:test-node',
    label: 'Test node',
    entityType: 'asset',
    assetType: 'service',
    clusterId: null,
    riskScore: 0.1,
    criticality: 0.4,
    status: 'normal',
    position: { x: 0, y: 24, z: 0 },
    color: '#36a9e1',
    statusColor: 'transparent',
    riskHaloColor: 'transparent',
    emissiveColor: '#2b5b70',
    sizeTier: 1,
    glyphShape: 'circle',
    size: 12,
    selected: false,
    highlighted: false,
    dimmed: false,
    evidenceMarked: false,
    incidentMarked: false,
    ...overrides,
  };
}

function makeInstancedMesh(count: number): THREE.InstancedMesh {
  return new THREE.InstancedMesh(
    new THREE.IcosahedronGeometry(1, 1),
    new THREE.MeshStandardMaterial(),
    count,
  );
}

describe('applyInstancedNodeAttributes', () => {
  it('applies per-instance base colors for every node in a snapshot-mounted scene', () => {
    // Mirrors the defect repro: a scene that mounts with all N nodes at once
    // (hydrated snapshot) must get distinct per-instance colors, not a
    // uniform fallback.
    const nodes = [
      makeSceneNode({ id: 'asset:svc', assetType: 'service', color: '#36a9e1' }),
      makeSceneNode({ id: 'asset:db', assetType: 'database', color: '#efb85a' }),
      makeSceneNode({ id: 'asset:ai', assetType: 'ai_model', color: '#cf88e8' }),
    ];
    const mesh = makeInstancedMesh(nodes.length);

    applyInstancedNodeAttributes(mesh, null, nodes);

    expect(mesh.instanceColor).not.toBeNull();
    const colors = mesh.instanceColor as THREE.InstancedBufferAttribute;
    // needsUpdate is a write-only setter that bumps `version`; a re-upload was
    // marked iff the version advanced past its initial 0.
    expect(colors.version).toBeGreaterThan(0);
    nodes.forEach((node, index) => {
      const expected = resolveThreeColor(node.color).color;
      expect(colors.getX(index)).toBeCloseTo(expected.r, 5);
      expect(colors.getY(index)).toBeCloseTo(expected.g, 5);
      expect(colors.getZ(index)).toBeCloseTo(expected.b, 5);
    });
    // The instance tint must not depend on a per-vertex `color` attribute:
    // the geometry never provides one, and the unbound attribute reads
    // (0,0,0) on ANGLE — declaring `vertexColors` blacks out every instance.
    expect(mesh.geometry.getAttribute('color')).toBeUndefined();
    expect((mesh.material as THREE.MeshStandardMaterial).vertexColors).toBe(false);
  });

  it('uploads the per-instance emissive accent attribute', () => {
    const nodes = [makeSceneNode({ emissiveColor: '#ff7078' })];
    const mesh = makeInstancedMesh(nodes.length);

    applyInstancedNodeAttributes(mesh, null, nodes);

    const emissive = mesh.geometry.getAttribute('instanceEmissive');
    expect(emissive).toBeDefined();
    const accent = resolveThreeColor('#ff7078').color;
    expect(emissive.getX(0)).toBeCloseTo(accent.r * 0.62, 5);
    expect(emissive.getY(0)).toBeCloseTo(accent.g * 0.62, 5);
    expect(emissive.getZ(0)).toBeCloseTo(accent.b * 0.62, 5);
  });

  it('mirrors matrices and accent colors onto the additive color coat', () => {
    const nodes = [makeSceneNode({ position: { x: 120, y: 60, z: -40 } })];
    const mesh = makeInstancedMesh(nodes.length);
    const coat = makeInstancedMesh(nodes.length);

    applyInstancedNodeAttributes(mesh, coat, nodes);

    expect(coat.instanceColor).not.toBeNull();
    const coatMatrix = new THREE.Matrix4();
    coat.getMatrixAt(0, coatMatrix);
    const coatPosition = new THREE.Vector3().setFromMatrixPosition(coatMatrix);
    expect(coatPosition.x).toBeCloseTo(120, 5);
    expect(coatPosition.y).toBeCloseTo(60, 5);
    expect(coatPosition.z).toBeCloseTo(-40, 5);
  });

  it('refreshes the cached instanced bounding sphere so raycasts hit after a warm remount', () => {
    const nodes = [
      makeSceneNode({ id: 'asset:far', position: { x: 500, y: 120, z: -300 } }),
      makeSceneNode({ id: 'asset:near', position: { x: -400, y: 80, z: 250 } }),
    ];
    const mesh = makeInstancedMesh(nodes.length);
    mesh.updateMatrixWorld(true);

    // Simulate the warm-remount race: three's first frustum/raycast pass runs
    // before the instance matrices are populated and caches a unit sphere at
    // the origin. `instanceMatrix.needsUpdate` never invalidates this cache.
    mesh.computeBoundingSphere();
    expect(mesh.boundingSphere?.radius ?? 0).toBeLessThan(2);

    applyInstancedNodeAttributes(mesh, null, nodes);
    mesh.updateMatrixWorld(true);

    // The sphere must now cover the laid-out instances…
    expect(mesh.boundingSphere?.radius ?? 0).toBeGreaterThan(100);

    // …and a ray aimed at a node must hit again (the defect left hover/click
    // permanently dead because this raycast tested the stale unit sphere).
    const raycaster = new THREE.Raycaster(
      new THREE.Vector3(500, 120, 1_000),
      new THREE.Vector3(0, 0, -1),
    );
    const hits = raycaster.intersectObject(mesh, false);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0]?.instanceId).toBe(0);
  });
});
