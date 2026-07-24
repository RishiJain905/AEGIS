import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import type { SceneNode } from '../contracts';
import { SCENE_NODE_SCHEMA_VERSION } from '../contracts';
import {
  applyInstancedNodeAttributes,
  applyPylonAttributes,
  nodeRadius,
} from './instanced-node-attributes';
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
    disclosed: true,
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

    applyInstancedNodeAttributes(mesh, nodes);

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

    applyInstancedNodeAttributes(mesh, nodes);

    const emissive = mesh.geometry.getAttribute('instanceEmissive');
    expect(emissive).toBeDefined();
    const accent = resolveThreeColor('#ff7078').color;
    expect(emissive.getX(0)).toBeCloseTo(accent.r * 0.62, 5);
    expect(emissive.getY(0)).toBeCloseTo(accent.g * 0.62, 5);
    expect(emissive.getZ(0)).toBeCloseTo(accent.b * 0.62, 5);
  });

  it('collapses undisclosed nodes to a dark husk with almost no emissive', () => {
    const nodes = [
      makeSceneNode({ id: 'asset:hidden', disclosed: false, emissiveColor: '#ff7078' }),
      makeSceneNode({ id: 'asset:visible', disclosed: true, emissiveColor: '#ff7078' }),
    ];
    const mesh = makeInstancedMesh(nodes.length);

    applyInstancedNodeAttributes(mesh, nodes);

    const colors = mesh.instanceColor as THREE.InstancedBufferAttribute;
    const emissive = mesh.geometry.getAttribute('instanceEmissive');
    const base = resolveThreeColor(nodes[0]?.color ?? '#36a9e1').color;
    // Fog-of-war base color moves well away from the disclosed asset color
    // (blue channel: the service cyan collapses toward the dark husk).
    expect(Math.abs(colors.getZ(0) - base.b)).toBeGreaterThan(0.1);
    // …and the emissive is an order of magnitude below the disclosed twin.
    expect(emissive.getX(0)).toBeLessThan(emissive.getX(1) * 0.2);
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

    applyInstancedNodeAttributes(mesh, nodes);
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

describe('applyPylonAttributes', () => {
  it('spans each pylon from the platform surface to just below the node body', () => {
    const node = makeSceneNode({ position: { x: 40, y: 60, z: -20 } });
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshBasicMaterial(),
      1,
    );

    applyPylonAttributes(mesh, [node]);

    const matrix = new THREE.Matrix4();
    mesh.getMatrixAt(0, matrix);
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    matrix.decompose(position, new THREE.Quaternion(), scale);

    expect(position.x).toBeCloseTo(40, 5);
    expect(position.z).toBeCloseTo(-20, 5);
    // Top of the pylon (center + half height) stays below the node center.
    expect(position.y + scale.y / 2).toBeLessThan(60);
    expect(position.y - scale.y / 2).toBeCloseTo(1.5, 3);
  });

  it('burns the whole column for compromised assets and dims fog-of-war stems', () => {
    const compromised = makeSceneNode({
      id: 'asset:burning',
      status: 'compromised',
      emissiveColor: '#ff7078',
    });
    const hidden = makeSceneNode({ id: 'asset:hidden', disclosed: false });
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshBasicMaterial(),
      2,
    );

    applyPylonAttributes(mesh, [compromised, hidden]);

    const colors = mesh.instanceColor as THREE.InstancedBufferAttribute;
    const accent = resolveThreeColor('#ff7078').color;
    expect(colors.getX(0)).toBeCloseTo(accent.r, 5);
    // The undisclosed stem is far darker than the burning column.
    expect(colors.getX(1)).toBeLessThan(colors.getX(0) * 0.25);
  });
});

describe('nodeRadius', () => {
  it('scales with size tier and selection', () => {
    const base = makeSceneNode();
    const selected = makeSceneNode({ selected: true });
    expect(nodeRadius(selected)).toBeGreaterThan(nodeRadius(base));
  });
});
