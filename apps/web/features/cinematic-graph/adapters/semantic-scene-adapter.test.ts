import { createGraphStore } from '@aegis/graph-domain';
import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { createSemanticSceneAdapter } from '@/features/cinematic-graph/adapters/semantic-scene-adapter';
import { RenderQualityTier, SemanticSceneAdapterError } from '@/features/cinematic-graph/contracts';
import { defaultGraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import shellDataset from '@/fixtures/shell-dataset.json';

describe('SemanticSceneAdapter', () => {
  it('projects the same canonical node and edge ids as GraphStore without inventing entities', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );

    const exported = store.exportSnapshot();
    expect(projection.nodeCount).toBe(exported.nodes.length);
    expect(projection.edgeCount).toBe(exported.edges.length);
    expect(projection.nodes.map((node) => node.id).sort()).toEqual(
      exported.nodes.map((node) => node.id).sort(),
    );
    expect(projection.edges.map((edge) => edge.id).sort()).toEqual(
      exported.edges.map((edge) => edge.id).sort(),
    );
    expect(projection.sequence).toBe(exported.sequence);
    expect(projection.revision).toBe(exported.revision);
    adapter.dispose();
  });

  it('frames the projected scene outside its full bounding radius on first sync', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );

    const cameraDistance = Math.hypot(
      projection.camera.position.x - projection.camera.target.x,
      projection.camera.position.y - projection.camera.target.y,
      projection.camera.position.z - projection.camera.target.z,
    );
    const maxNodeDistance = Math.max(
      ...projection.nodes.map((node) =>
        Math.hypot(
          node.position.x - projection.camera.target.x,
          node.position.y - projection.camera.target.y,
          node.position.z - projection.camera.target.z,
        ),
      ),
    );

    expect(cameraDistance).toBeGreaterThan(maxNodeDistance * 1.25);
    adapter.dispose();
  });

  it('lays the theater out from canonical clusters, ignoring 2D drag positions', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    const sigmaPositions = Object.fromEntries(
      snapshot.nodes.map((node, index) => [
        node.id,
        {
          x: (index % 8) * 130 - 455,
          y: Math.floor(index / 8) * 400 - 800,
        },
      ]),
    );

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      {
        nodePositions: sigmaPositions,
        qualityTier: RenderQualityTier.HIGH,
      },
    );

    // One sector platform per distinct clusterId in the fixture.
    const clusterIds = new Set(
      snapshot.nodes.map((node) => node.clusterId).filter((id): id is string => Boolean(id)),
    );
    expect(projection.zones.map((zone) => zone.id).sort()).toEqual([...clusterIds].sort());

    // Every node sits on its own platform footprint, regardless of the 2D
    // drag positions passed in (the 3D architecture is intrinsic).
    const zoneById = new Map(projection.zones.map((zone) => [zone.id, zone]));
    for (const node of projection.nodes) {
      const zone = node.clusterId ? zoneById.get(node.clusterId) : undefined;
      expect(zone).toBeDefined();
      const distance = Math.hypot(
        node.position.x - (zone?.center.x ?? 0),
        node.position.z - (zone?.center.z ?? 0),
      );
      expect(distance).toBeLessThanOrEqual(zone?.radius ?? 0);
    }

    // The whole ring stays inside a bounded, renderable world span.
    const xs = projection.nodes.map((node) => node.position.x);
    const zs = projection.nodes.map((node) => node.position.z);
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThanOrEqual(1_600);
    expect(Math.max(...zs) - Math.min(...zs)).toBeLessThanOrEqual(1_600);
    adapter.dispose();
  });

  it('rolls zone alert levels up from disclosed statuses only', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[1]);
    const compromisedId = snapshot.nodes.find((node) => node.clusterId)?.id;
    const compromisedCluster = snapshot.nodes.find((node) => node.clusterId)?.clusterId;
    const doctored = {
      ...snapshot,
      nodes: snapshot.nodes.map((node) => {
        if (node.id === compromisedId) {
          return { ...node, status: 'compromised' as const, disclosed: true };
        }
        if (node.clusterId === compromisedCluster) {
          // A second hostile node in the same zone stays undisclosed — fog of
          // war must keep it from raising the platform alert on its own.
          return { ...node, status: 'suspicious' as const, disclosed: false };
        }
        return { ...node, disclosed: true };
      }),
    };
    const store = createGraphStore();
    store.loadSnapshot(parseContract(graphSnapshotSchema, doctored));
    const adapter = createSemanticSceneAdapter();

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );

    const hotZone = projection.zones.find((zone) => zone.id === compromisedCluster);
    expect(hotZone?.alertLevel).toBe('critical');
    for (const zone of projection.zones) {
      if (zone.id !== compromisedCluster) {
        expect(zone.alertLevel).toBe('calm');
      }
    }

    // The undisclosed hostile keeps its dark-husk projection.
    const hidden = projection.nodes.find(
      (node) => node.clusterId === compromisedCluster && node.id !== compromisedId,
    );
    expect(hidden?.disclosed).toBe(false);
    expect(hidden?.statusColor).toBe('transparent');
    adapter.dispose();
  });

  it('maps risk, status, and evidence markers from canonical fields only', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    const gateway = snapshot.nodes.find((node) => node.id === 'asset:svc-api-gateway');
    expect(gateway).toBeDefined();

    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      {
        ...defaultGraphVisualState,
        overlayToggles: {
          risk: true,
          status: true,
          evidence: true,
          incident: true,
        },
        selection: {
          schemaVersion: 1,
          primaryNodeId: 'asset:svc-api-gateway',
          secondaryNodeId: null,
          selectedEdgeId: null,
        },
      },
      {
        qualityTier: RenderQualityTier.HIGH,
        evidenceNodeIds: new Set(['asset:svc-api-gateway']),
        incidentNodeIds: new Set(['asset:svc-api-gateway']),
      },
    );

    const sceneNode = projection.nodes.find((node) => node.id === 'asset:svc-api-gateway');
    expect(sceneNode).toBeDefined();
    expect(sceneNode?.riskScore).toBe(gateway?.riskScore);
    expect(sceneNode?.status).toBe(gateway?.status);
    expect(sceneNode?.selected).toBe(true);
    expect(sceneNode?.evidenceMarked).toBe(true);
    expect(sceneNode?.incidentMarked).toBe(true);
    adapter.dispose();
  });

  it('returns empty projection for fallback2d tier without inventing scene entities', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    const projection = adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.FALLBACK_2D },
    );
    expect(projection.nodeCount).toBe(0);
    expect(projection.edgeCount).toBe(0);
    expect(projection.qualityTier).toBe(RenderQualityTier.FALLBACK_2D);
    adapter.dispose();
  });

  it('fails safely after dispose and clears last projection', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.MEDIUM },
    );
    expect(adapter.getLastProjection()).not.toBeNull();
    adapter.dispose();
    expect(adapter.getLastProjection()).toBeNull();
    expect(() =>
      adapter.syncFromStore(
        store,
        defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
        defaultGraphVisualState,
      ),
    ).toThrow(SemanticSceneAdapterError);
  });

  it('preserves focus selection via stable entity ids', () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    const adapter = createSemanticSceneAdapter();
    adapter.syncFromStore(
      store,
      defaultGraphVisualState.filterSet as import('@aegis/graph-domain').GraphFilterSet,
      defaultGraphVisualState,
      { qualityTier: RenderQualityTier.HIGH },
    );
    const bookmark = adapter.focusNode('asset:svc-api-gateway');
    expect(bookmark).not.toBeNull();
    expect(bookmark?.target).toEqual(
      adapter.getLastProjection()?.nodes.find((node) => node.id === 'asset:svc-api-gateway')
        ?.position,
    );
    adapter.dispose();
  });
});
