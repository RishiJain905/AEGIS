import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';
import type Graph from 'graphology';

import type { LodRenderHints } from './lod-policy';
import type { GraphVisualState } from './graph-visual-state';

export interface RenderGraphProjection {
  visibleNodeIds: string[];
  visibleEdgeIds: string[];
  nodeCount: number;
  edgeCount: number;
}

export interface SyncFromStoreOptions {
  lodHints?: LodRenderHints;
  workerPositions?: Record<string, { x: number; y: number }>;
  zoomRatio?: number;
  evidenceNodeIds?: ReadonlySet<string>;
  incidentNodeIds?: ReadonlySet<string>;
}

export interface OperationalGraphAdapter {
  getPresentationGraph(): Graph;
  syncFromStore(
    store: GraphStore,
    filterSet: GraphFilterSet,
    visualState: GraphVisualState,
    options?: SyncFromStoreOptions,
  ): RenderGraphProjection;
  applyHighlight(
    store: GraphStore,
    visualState: GraphVisualState,
  ): { highlightedNodeIds: string[]; highlightedEdgeIds: string[] };
  focusNode(nodeId: string): void;
  fitGraph(): void;
  zoomIn(): void;
  zoomOut(): void;
  resetCamera(): void;
  resize(): void;
  dispose(): void;
}

export interface OperationalGraphAdapterFactory {
  create(container: HTMLElement): OperationalGraphAdapter;
}
