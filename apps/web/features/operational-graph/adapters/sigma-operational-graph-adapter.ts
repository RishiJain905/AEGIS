import Graph from 'graphology';
import Sigma from 'sigma';

import type { GraphEdgeV1, GraphNodeV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import type {
  OperationalGraphAdapter,
  RenderGraphProjection,
} from '../contracts/operational-graph-adapter';
import { GraphHighlightMode, type GraphVisualState } from '../contracts/graph-visual-state';
import { computeInitialLayout } from '../layout/initial-layout';
import {
  getEdgeVisualStyle,
  getHighlightColor,
  getNodeVisualStyle,
  getRiskHaloColor,
} from '../semantic/graph-semantic-styles';

const DEFAULT_EDGE_COLOR = '#94a3b866';
const DIMMED_OPACITY = 0.15;

function buildEntityMaps(snapshot: GraphSnapshotV1): {
  nodes: Map<string, GraphNodeV1>;
  edges: Map<string, GraphEdgeV1>;
} {
  const nodes = new Map<string, GraphNodeV1>();
  const edges = new Map<string, GraphEdgeV1>();
  for (const node of snapshot.nodes) {
    nodes.set(node.id, node);
  }
  for (const edge of snapshot.edges) {
    edges.set(edge.id, edge);
  }
  return { nodes, edges };
}

export class SigmaOperationalGraphAdapter implements OperationalGraphAdapter {
  private readonly graph: Graph;
  private sigma: Sigma | null = null;
  private readonly container: HTMLElement;
  private reducedMotion = false;

  constructor(container: HTMLElement, reducedMotion = false) {
    this.container = container;
    this.reducedMotion = reducedMotion;
    this.graph = new Graph({ multi: false, type: 'directed' });
  }

  getPresentationGraph(): Graph {
    return this.graph;
  }

  mount(): Sigma {
    if (this.sigma) {
      return this.sigma;
    }
    this.sigma = new Sigma(this.graph, this.container, {
      renderEdgeLabels: false,
      allowInvalidContainer: false,
      defaultNodeColor: '#64748b',
      defaultEdgeColor: DEFAULT_EDGE_COLOR,
      labelRenderedSizeThreshold: 6,
      labelDensity: 0.5,
      zIndex: true,
    });
    return this.sigma;
  }

  setReducedMotion(reduced: boolean): void {
    this.reducedMotion = reduced;
  }

  syncFromStore(
    store: GraphStore,
    filterSet: GraphFilterSet,
    visualState: GraphVisualState,
  ): RenderGraphProjection {
    const snapshot = store.exportSnapshot();
    const filtered = store.applyFilters(filterSet);
    const entityMaps = buildEntityMaps(snapshot);

    const positions = computeInitialLayout(
      snapshot.nodes.filter((n) => filtered.visibleNodeIds.includes(n.id)),
      snapshot.clusters,
      visualState.nodePositions,
    );

    const visibleSet = new Set(filtered.visibleNodeIds);
    const highlightNodes = new Set(visualState.highlightedNodeIds);
    const highlightEdges = new Set(visualState.highlightedEdgeIds);
    const isIsolation = visualState.isolationActive && highlightNodes.size > 0;

    for (const nodeId of this.graph.nodes()) {
      if (!visibleSet.has(nodeId)) {
        if (this.graph.hasNode(nodeId)) {
          this.graph.dropNode(nodeId);
        }
      }
    }

    for (const nodeId of filtered.visibleNodeIds) {
      const canonical = entityMaps.nodes.get(nodeId);
      if (!canonical) {
        continue;
      }
      const pos = positions[nodeId] ?? { x: 0, y: 0 };
      const style = getNodeVisualStyle(canonical);
      const isHighlighted = highlightNodes.has(nodeId);
      const isDimmed = isIsolation && !isHighlighted;
      const isHovered = visualState.hoveredNodeId === nodeId;
      const isSelected = visualState.selection.primaryNodeId === nodeId;

      const attrs = {
        x: pos.x,
        y: pos.y,
        size: style.size + (isSelected ? 4 : 0) + (isHovered ? 2 : 0),
        color: isDimmed ? `${style.color}33` : style.color,
        label: canonical.label,
        borderColor: style.borderColor,
        zIndex: isSelected ? 2 : isHighlighted ? 1 : 0,
        riskHalo: visualState.overlayToggles.risk
          ? getRiskHaloColor(style.riskBand)
          : 'transparent',
        statusIndicator: visualState.overlayToggles.status ? style.statusColor : 'transparent',
      };

      if (this.graph.hasNode(nodeId)) {
        this.graph.mergeNodeAttributes(nodeId, attrs);
      } else {
        this.graph.addNode(nodeId, attrs);
      }
    }

    const visibleEdgeSet = new Set(filtered.visibleEdgeIds);
    for (const edgeId of this.graph.edges()) {
      const attrs = this.graph.getEdgeAttributes(edgeId);
      const key = attrs.key as string;
      if (!visibleEdgeSet.has(key)) {
        this.graph.dropEdge(edgeId);
      }
    }

    for (const edgeId of filtered.visibleEdgeIds) {
      const canonical = entityMaps.edges.get(edgeId);
      if (!canonical) {
        continue;
      }
      if (!this.graph.hasNode(canonical.source) || !this.graph.hasNode(canonical.target)) {
        continue;
      }

      const edgeStyle = getEdgeVisualStyle(canonical);
      const isHighlighted = highlightEdges.has(edgeId);
      const isDimmed = isIsolation && !isHighlighted;
      let highlightColor = edgeStyle.color;
      if (visualState.highlightMode !== GraphHighlightMode.NONE) {
        switch (visualState.highlightMode) {
          case GraphHighlightMode.NEIGHBORHOOD:
            highlightColor = getHighlightColor('neighborhood');
            break;
          case GraphHighlightMode.PATH:
            highlightColor = getHighlightColor('path');
            break;
          case GraphHighlightMode.INCIDENT:
            highlightColor = getHighlightColor('incident');
            break;
          case GraphHighlightMode.DEPENDENCIES:
            highlightColor = getHighlightColor('dependencies');
            break;
          default: {
            const _exhaustive: never = visualState.highlightMode;
            throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
          }
        }
      }

      const attrs = {
        key: edgeId,
        size: isHighlighted ? edgeStyle.size * 2 : edgeStyle.size,
        color: isDimmed ? DEFAULT_EDGE_COLOR : isHighlighted ? highlightColor : edgeStyle.color,
        type: edgeStyle.type,
        opacity: isDimmed ? DIMMED_OPACITY : isHighlighted ? 1 : edgeStyle.opacity,
        zIndex: isHighlighted ? 1 : 0,
      };

      const existingEdge = this.graph.edges().find((e) => {
        const a = this.graph.getEdgeAttributes(e);
        return a.key === edgeId;
      });

      if (existingEdge) {
        this.graph.mergeEdgeAttributes(existingEdge, attrs);
      } else {
        this.graph.addEdge(canonical.source, canonical.target, attrs);
      }
    }

    this.sigma?.refresh();

    return {
      visibleNodeIds: filtered.visibleNodeIds,
      visibleEdgeIds: filtered.visibleEdgeIds,
      nodeCount: filtered.visibleNodeIds.length,
      edgeCount: filtered.visibleEdgeIds.length,
    };
  }

  applyHighlight(
    store: GraphStore,
    visualState: GraphVisualState,
  ): { highlightedNodeIds: string[]; highlightedEdgeIds: string[] } {
    const { highlightMode, selection } = visualState;

    if (highlightMode === GraphHighlightMode.NONE || !selection.primaryNodeId) {
      return { highlightedNodeIds: [], highlightedEdgeIds: [] };
    }

    switch (highlightMode) {
      case GraphHighlightMode.NEIGHBORHOOD: {
        const result = store.getNeighborhood(selection.primaryNodeId, { hops: 1 });
        return { highlightedNodeIds: result.nodeIds, highlightedEdgeIds: result.edgeIds };
      }
      case GraphHighlightMode.PATH: {
        if (!selection.secondaryNodeId) {
          return { highlightedNodeIds: [selection.primaryNodeId], highlightedEdgeIds: [] };
        }
        const pathResult = store.queryPaths({
          schemaVersion: 1,
          runId: store.getRunId() ?? '',
          sourceId: selection.primaryNodeId,
          targetId: selection.secondaryNodeId,
          maxHops: 8,
          relationshipTypes: [],
          directedOnly: false,
        });
        const path = pathResult.paths[0] ?? [];
        const edgeIds: string[] = [];
        for (let i = 0; i < path.length - 1; i += 1) {
          const snapshot = store.exportSnapshot();
          for (const edge of snapshot.edges) {
            if (
              (edge.source === path[i] && edge.target === path[i + 1]) ||
              (edge.source === path[i + 1] && edge.target === path[i])
            ) {
              edgeIds.push(edge.id);
            }
          }
        }
        return { highlightedNodeIds: path, highlightedEdgeIds: edgeIds };
      }
      case GraphHighlightMode.INCIDENT: {
        const result = store.getIncidentSubgraph([selection.primaryNodeId], { hops: 2 });
        return { highlightedNodeIds: result.nodeIds, highlightedEdgeIds: result.edgeIds };
      }
      case GraphHighlightMode.DEPENDENCIES: {
        const deps = store.getDependencies(selection.primaryNodeId, 3);
        return {
          highlightedNodeIds: [selection.primaryNodeId, ...deps],
          highlightedEdgeIds: [],
        };
      }
      default: {
        const _exhaustive: never = highlightMode;
        throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
      }
    }
  }

  focusNode(nodeId: string): void {
    if (!this.sigma || !this.graph.hasNode(nodeId)) {
      return;
    }
    const attrs = this.graph.getNodeAttributes(nodeId);
    void this.sigma
      .getCamera()
      .animate(
        { x: attrs.x as number, y: attrs.y as number, ratio: 0.4 },
        { duration: this.reducedMotion ? 0 : 300 },
      );
  }

  fitGraph(): void {
    if (!this.sigma) {
      return;
    }
    void this.sigma.getCamera().animatedReset({ duration: this.reducedMotion ? 0 : 300 });
  }

  zoomIn(): void {
    if (!this.sigma) {
      return;
    }
    const camera = this.sigma.getCamera();
    void camera.animate({ ratio: camera.ratio * 0.7 }, { duration: this.reducedMotion ? 0 : 200 });
  }

  zoomOut(): void {
    if (!this.sigma) {
      return;
    }
    const camera = this.sigma.getCamera();
    void camera.animate({ ratio: camera.ratio * 1.4 }, { duration: this.reducedMotion ? 0 : 200 });
  }

  resetCamera(): void {
    this.fitGraph();
  }

  dispose(): void {
    if (this.sigma) {
      this.sigma.kill();
      this.sigma = null;
    }
    this.graph.clear();
  }
}

export function createSigmaOperationalGraphAdapter(
  container: HTMLElement,
  reducedMotion = false,
): SigmaOperationalGraphAdapter {
  return new SigmaOperationalGraphAdapter(container, reducedMotion);
}
