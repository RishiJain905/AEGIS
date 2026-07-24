import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import type { GraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import {
  defaultCameraBookmark3D,
  defaultCapabilityReport,
  RenderQualityTier,
  SemanticSceneAdapterError,
  type CameraBookmark3D,
  type CapabilityReport,
  type SceneProjection,
  type SemanticSceneAdapter,
  type SyncSceneOptions,
} from '../contracts';
import { computeLayerEmphasis } from '@/features/operational-graph/semantic/layer-emphasis';
import { EdgeActivityTracker } from '@/features/operational-graph/semantic/edge-activity';

import { mapCanonicalEdgeToSceneEdge, mapCanonicalNodeToSceneNode } from '../lib/semantic-mapping';
import { computeZoneLayout, zoneAlertLevel } from '../lib/zone-layout';
import { focusNodeBookmark, frameSceneNodes } from '../lib/camera-framing';
import { SCENE_ZONE_SCHEMA_VERSION, type SceneZone } from '../contracts/scene-zone';

export class SemanticSceneAdapterImpl implements SemanticSceneAdapter {
  private lastProjection: SceneProjection | null = null;
  /** Nodes + platform proxies, so camera framing covers the architecture. */
  private frameables: Array<{ position: { x: number; y: number; z: number }; size: number }> = [];
  private readonly edgeActivity = new EdgeActivityTracker();
  private capabilityReport: CapabilityReport = defaultCapabilityReport;
  private camera: CameraBookmark3D = defaultCameraBookmark3D;
  private automaticCamera = true;
  private disposed = false;

  syncFromStore(
    store: GraphStore,
    filterSet: GraphFilterSet,
    visualState: GraphVisualState,
    options: SyncSceneOptions = {},
  ): SceneProjection {
    this.assertNotDisposed();

    let snapshot;
    try {
      snapshot = store.exportSnapshot();
    } catch (error) {
      throw new SemanticSceneAdapterError(
        'graph_export_failed',
        error instanceof Error ? error.message : 'Failed to export graph snapshot',
      );
    }

    if (!Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.edges)) {
      throw new SemanticSceneAdapterError(
        'graph_snapshot_invalid',
        'Graph snapshot is missing required node or edge collections',
      );
    }

    const qualityTier = options.qualityTier ?? this.capabilityReport.recommendedTier;

    if (qualityTier === RenderQualityTier.FALLBACK_2D) {
      const empty: SceneProjection = {
        nodes: [],
        edges: [],
        zones: [],
        nodeCount: 0,
        edgeCount: 0,
        sequence: snapshot.sequence,
        revision: snapshot.revision,
        runId: snapshot.runId,
        qualityTier,
        camera: this.camera,
      };
      this.lastProjection = empty;
      return empty;
    }

    const filtered = store.applyFilters(filterSet);
    const visibleNodeIds = new Set(filtered.visibleNodeIds);
    const visibleEdgeIds = new Set(filtered.visibleEdgeIds);
    const visibleNodes = snapshot.nodes.filter((node) => visibleNodeIds.has(node.id));
    // Bastion-ring layout: platform-per-cluster placement derived purely from
    // canonical node/cluster data. 2D drag positions intentionally do not
    // leak in — the 3D theater has its own intrinsic architecture.
    const { positions, zones: zonePlacements } = computeZoneLayout(
      visibleNodes,
      snapshot.clusters,
    );

    const evidenceNodeIds = options.evidenceNodeIds ?? new Set<string>();
    const incidentNodeIds = options.incidentNodeIds ?? new Set<string>();
    const emphasis = computeLayerEmphasis(
      { nodes: snapshot.nodes, edges: snapshot.edges },
      filterSet.enabledLayers,
    );

    const nodes = visibleNodes.map((node) => {
      const position = positions[node.id] ?? { x: 0, y: 0, z: 0 };
      return mapCanonicalNodeToSceneNode({
        node,
        position,
        visualState,
        evidenceMarked: evidenceNodeIds.has(node.id),
        incidentMarked: incidentNodeIds.has(node.id),
        layerDimmed: emphasis.dimmedNodeIds.has(node.id),
      });
    });

    // Pulse detection (§7.9) runs on the same sync tick the GraphStore delta
    // landed on — an edge lights up when its relationship receives a new event.
    this.edgeActivity.update(snapshot.edges);

    const nodeIdSet = new Set(nodes.map((node) => node.id));
    const edges = snapshot.edges
      .filter((edge) => visibleEdgeIds.has(edge.id))
      .filter((edge) => nodeIdSet.has(edge.source) && nodeIdSet.has(edge.target))
      .map((edge) =>
        mapCanonicalEdgeToSceneEdge({
          edge,
          visualState,
          layerDimmed: emphasis.dimmedEdgeIds.has(edge.id),
          pulseAt: this.edgeActivity.getPulseAt(edge.id),
        }),
      );

    // Zone alert rollup over disclosed member statuses only — fog of war
    // means an undetected asset can never tint its platform.
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const zones: SceneZone[] = zonePlacements.map((placement) => ({
      schemaVersion: SCENE_ZONE_SCHEMA_VERSION,
      id: placement.id,
      label: placement.label,
      center: placement.center,
      radius: placement.radius,
      angle: placement.angle,
      alertLevel: zoneAlertLevel(
        placement.nodeIds
          .map((nodeId) => nodeById.get(nodeId))
          .filter((node): node is NonNullable<typeof node> => node !== undefined && node.disclosed)
          .map((node) => node.status),
      ),
      nodeCount: placement.nodeIds.length,
    }));

    // Frame automatically only on the first projection; afterwards the camera
    // belongs to the operator (orbit) or explicit focus/reset actions, so live
    // graph revisions never yank the viewpoint. Framing covers the platforms,
    // not just the nodes, so the ring's architecture is in the opening shot.
    this.frameables = [
      ...nodes.map((node) => ({ position: node.position, size: node.size })),
      ...zones.map((zone) => ({ position: zone.center, size: zone.radius })),
    ];
    if (this.automaticCamera && this.lastProjection === null) {
      this.camera = frameSceneNodes(this.frameables, this.camera.fov);
    }

    const projection: SceneProjection = {
      nodes,
      edges,
      zones,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      sequence: snapshot.sequence,
      revision: snapshot.revision,
      runId: snapshot.runId,
      qualityTier,
      camera: this.camera,
    };
    this.lastProjection = projection;
    return projection;
  }

  getLastProjection(): SceneProjection | null {
    return this.lastProjection;
  }

  setCapabilityReport(report: CapabilityReport): void {
    this.assertNotDisposed();
    this.capabilityReport = report;
  }

  getCapabilityReport(): CapabilityReport {
    return this.capabilityReport;
  }

  setCameraBookmark(bookmark: CameraBookmark3D): void {
    this.assertNotDisposed();
    this.camera = bookmark;
    this.automaticCamera = false;
  }

  getCameraBookmark(): CameraBookmark3D {
    return this.camera;
  }

  focusNode(nodeId: string): CameraBookmark3D | null {
    this.assertNotDisposed();
    const projectionNodes = this.lastProjection?.nodes ?? [];
    const node = projectionNodes.find((entry) => entry.id === nodeId);
    if (!node) {
      return null;
    }
    const bookmark = focusNodeBookmark(node, this.camera, this.frameables);
    this.camera = bookmark;
    this.automaticCamera = false;
    return bookmark;
  }

  resetCamera(): CameraBookmark3D {
    this.assertNotDisposed();
    this.automaticCamera = true;
    this.camera = frameSceneNodes(this.frameables, defaultCameraBookmark3D.fov);
    return this.camera;
  }

  /** §7.7 zoom: dolly the orbit camera along its current view direction,
   * clamped to the same distance envelope as the OrbitControls. */
  zoomCamera(factor: number): CameraBookmark3D {
    this.assertNotDisposed();
    const { position, target } = this.camera;
    const direction = {
      x: position.x - target.x,
      y: position.y - target.y,
      z: position.z - target.z,
    };
    const length = Math.hypot(direction.x, direction.y, direction.z) || 1;
    const nextLength = Math.min(6_500, Math.max(60, length * factor));
    const scale = nextLength / length;
    this.camera = {
      schemaVersion: 1,
      position: {
        x: target.x + direction.x * scale,
        y: target.y + direction.y * scale,
        z: target.z + direction.z * scale,
      },
      target: { ...target },
      fov: this.camera.fov,
    };
    this.automaticCamera = false;
    return this.camera;
  }

  dispose(): void {
    this.lastProjection = null;
    this.frameables = [];
    this.edgeActivity.clear();
    this.capabilityReport = defaultCapabilityReport;
    this.camera = defaultCameraBookmark3D;
    this.automaticCamera = true;
    this.disposed = true;
  }

  private assertNotDisposed(): void {
    if (this.disposed) {
      throw new SemanticSceneAdapterError(
        'adapter_disposed',
        'SemanticSceneAdapter has been disposed',
      );
    }
  }
}

export function createSemanticSceneAdapter(): SemanticSceneAdapter {
  return new SemanticSceneAdapterImpl();
}
