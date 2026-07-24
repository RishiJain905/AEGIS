import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import type { GraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import type { CameraBookmark3D } from './camera-bookmark-3d';
import type { CapabilityReport } from './capability-report';
import type { RenderQualityTierValue } from './render-quality-tier';
import type { SceneEdge } from './scene-edge';
import type { SceneNode } from './scene-node';
import type { SceneZone } from './scene-zone';

export interface SceneProjection {
  nodes: SceneNode[];
  edges: SceneEdge[];
  /** Sector platforms of the bastion ring, derived from graph clusters. */
  zones: SceneZone[];
  nodeCount: number;
  edgeCount: number;
  sequence: number;
  revision: number;
  runId: string;
  qualityTier: RenderQualityTierValue;
  camera: CameraBookmark3D;
}

export interface SyncSceneOptions {
  /** Accepted for API compatibility; the 3D layout is intrinsic (zone
   * architecture) and no longer mirrors 2D drag positions. */
  nodePositions?: Record<string, { x: number; y: number }>;
  workerPositions?: Record<string, { x: number; y: number }>;
  qualityTier?: RenderQualityTierValue;
  evidenceNodeIds?: ReadonlySet<string>;
  incidentNodeIds?: ReadonlySet<string>;
}

export interface SemanticSceneAdapter {
  syncFromStore(
    store: GraphStore,
    filterSet: GraphFilterSet,
    visualState: GraphVisualState,
    options?: SyncSceneOptions,
  ): SceneProjection;
  getLastProjection(): SceneProjection | null;
  setCapabilityReport(report: CapabilityReport): void;
  getCapabilityReport(): CapabilityReport;
  setCameraBookmark(bookmark: CameraBookmark3D): void;
  getCameraBookmark(): CameraBookmark3D;
  focusNode(nodeId: string): CameraBookmark3D | null;
  resetCamera(): CameraBookmark3D;
  /** §7.7: dolly the orbit camera toward (<1) or away from (>1) its target. */
  zoomCamera(factor: number): CameraBookmark3D;
  dispose(): void;
}

export class SemanticSceneAdapterError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'SemanticSceneAdapterError';
    this.code = code;
  }
}
