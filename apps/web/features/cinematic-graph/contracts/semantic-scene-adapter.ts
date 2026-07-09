import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import type { GraphVisualState } from '@/features/operational-graph/contracts/graph-visual-state';

import type { CameraBookmark3D } from './camera-bookmark-3d';
import type { CapabilityReport } from './capability-report';
import type { RenderQualityTierValue } from './render-quality-tier';
import type { SceneEdge } from './scene-edge';
import type { SceneNode } from './scene-node';

export interface SceneProjection {
  nodes: SceneNode[];
  edges: SceneEdge[];
  nodeCount: number;
  edgeCount: number;
  sequence: number;
  revision: number;
  runId: string;
  qualityTier: RenderQualityTierValue;
  camera: CameraBookmark3D;
}

export interface SyncSceneOptions {
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
