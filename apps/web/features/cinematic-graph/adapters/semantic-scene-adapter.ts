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
import { mapCanonicalEdgeToSceneEdge, mapCanonicalNodeToSceneNode } from '../lib/semantic-mapping';
import { normalizeScenePositions, resolveStablePositions } from '../lib/stable-positions';
import { frameSceneNodes } from '../lib/camera-framing';

export class SemanticSceneAdapterImpl implements SemanticSceneAdapter {
  private lastProjection: SceneProjection | null = null;
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
    const positions = normalizeScenePositions(
      resolveStablePositions(
        visibleNodes,
        snapshot.clusters,
        {
          ...visualState.nodePositions,
          ...(options.nodePositions ?? {}),
        },
        options.workerPositions ?? {},
      ),
    );

    const evidenceNodeIds = options.evidenceNodeIds ?? new Set<string>();
    const incidentNodeIds = options.incidentNodeIds ?? new Set<string>();

    const nodes = visibleNodes.map((node) => {
      const position = positions[node.id] ?? { x: 0, y: 0, z: 0 };
      return mapCanonicalNodeToSceneNode({
        node,
        position,
        visualState,
        evidenceMarked: evidenceNodeIds.has(node.id),
        incidentMarked: incidentNodeIds.has(node.id),
      });
    });

    const nodeIdSet = new Set(nodes.map((node) => node.id));
    const edges = snapshot.edges
      .filter((edge) => visibleEdgeIds.has(edge.id))
      .filter((edge) => nodeIdSet.has(edge.source) && nodeIdSet.has(edge.target))
      .map((edge) => mapCanonicalEdgeToSceneEdge({ edge, visualState }));

    if (this.automaticCamera) {
      this.camera = frameSceneNodes(nodes, this.camera.fov);
    }

    const projection: SceneProjection = {
      nodes,
      edges,
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
    const node = this.lastProjection?.nodes.find((entry) => entry.id === nodeId);
    if (!node) {
      return null;
    }
    const bookmark: CameraBookmark3D = {
      schemaVersion: 1,
      position: {
        x: node.position.x,
        y: node.position.y + 80,
        z: node.position.z + 160,
      },
      target: { ...node.position },
      fov: this.camera.fov,
    };
    this.camera = bookmark;
    this.automaticCamera = false;
    return bookmark;
  }

  resetCamera(): CameraBookmark3D {
    this.assertNotDisposed();
    this.automaticCamera = true;
    this.camera = frameSceneNodes(this.lastProjection?.nodes ?? [], defaultCameraBookmark3D.fov);
    return this.camera;
  }

  dispose(): void {
    this.lastProjection = null;
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
