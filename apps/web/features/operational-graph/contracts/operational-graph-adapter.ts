import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';
import type Graph from 'graphology';

import type { GraphVisualState } from './graph-visual-state';

export interface RenderGraphProjection {
  visibleNodeIds: string[];
  visibleEdgeIds: string[];
  nodeCount: number;
  edgeCount: number;
}

export interface OperationalGraphAdapter {
  getPresentationGraph(): Graph;
  syncFromStore(
    store: GraphStore,
    filterSet: GraphFilterSet,
    visualState: GraphVisualState,
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
  dispose(): void;
}

export interface OperationalGraphAdapterFactory {
  create(container: HTMLElement): OperationalGraphAdapter;
}
