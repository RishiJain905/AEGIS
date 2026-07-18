import Graph from 'graphology';
import Sigma from 'sigma';

import type { GraphEdgeV1, GraphNodeV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import type { GraphFilterSet, GraphStore } from '@aegis/graph-domain';

import type {
  OperationalGraphAdapter,
  RenderGraphProjection,
  SyncFromStoreOptions,
} from '../contracts/operational-graph-adapter';
import { GraphHighlightMode, type GraphVisualState } from '../contracts/graph-visual-state';
import { LabelMode } from '../contracts/lod-policy';
import { computeInitialLayout } from '../layout/initial-layout';
import { buildClusterPresentationNodes } from '../performance/cluster-presentation';
import {
  getEdgeVisualStyle,
  getHighlightColor,
  getNodeVisualStyle,
  getRiskHaloColor,
} from '../semantic/graph-semantic-styles';
import { drawAegisNodeHover, drawAegisNodeLabel } from '../rendering/aegis-canvas-renderers';

const DIMMED_OPACITY = 0.15;

const NODE_SHAPES: Record<string, 'circle' | 'diamond' | 'square' | 'triangle' | 'hexagon'> = {
  service: 'circle',
  device: 'diamond',
  database: 'square',
  identity: 'hexagon',
  user: 'hexagon',
  control: 'triangle',
  ai_model: 'hexagon',
};

function colorWithOpacity(color: string, opacity: number): string {
  const match = color.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!match) {
    return color;
  }
  const [, red = '00', green = '00', blue = '00'] = match;
  return `rgba(${String(Number.parseInt(red, 16))}, ${String(Number.parseInt(green, 16))}, ${String(Number.parseInt(blue, 16))}, ${String(Math.min(1, Math.max(0, opacity)))})`;
}

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

function shouldRenderLabel(
  labelMode: (typeof LabelMode)[keyof typeof LabelMode],
  isSelected: boolean,
  isHighlighted: boolean,
  isHovered: boolean,
): boolean {
  switch (labelMode) {
    case LabelMode.ALL:
      return true;
    case LabelMode.SELECTED:
      return isSelected || isHighlighted || isHovered;
    case LabelMode.NONE:
      return false;
    default: {
      const _exhaustive: never = labelMode;
      throw new Error(`Unhandled label mode: ${String(_exhaustive)}`);
    }
  }
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
      defaultNodeColor: '#718397',
      defaultEdgeColor: '#61788c',
      labelFont: '"Cascadia Mono", "Segoe UI", sans-serif',
      labelSize: 11,
      labelWeight: '600',
      labelColor: { color: '#d7e5ef' },
      labelRenderedSizeThreshold: 9,
      labelDensity: 0.72,
      labelGridCellSize: 140,
      stagePadding: 52,
      hideLabelsOnMove: false,
      hideEdgesOnMove: false,
      defaultDrawNodeLabel: drawAegisNodeLabel,
      defaultDrawNodeHover: drawAegisNodeHover,
      minEdgeThickness: 0.75,
      minCameraRatio: 0.06,
      maxCameraRatio: 6,
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
    options: SyncFromStoreOptions = {},
  ): RenderGraphProjection {
    const snapshot = store.exportSnapshot();
    const filtered = store.applyFilters(filterSet);
    const entityMaps = buildEntityMaps(snapshot);
    const lodHints = options.lodHints;
    const collapsedClusterIds = lodHints?.collapsedClusterIds ?? visualState.collapsedClusterIds;

    const visibleNodes = snapshot.nodes.filter((node) => filtered.visibleNodeIds.includes(node.id));
    const { presentationNodes, hiddenNodeIds } = buildClusterPresentationNodes(
      visibleNodes,
      snapshot.clusters,
      collapsedClusterIds,
    );

    const layoutPositions = computeInitialLayout(
      visibleNodes,
      snapshot.clusters,
      visualState.nodePositions,
    );
    const positions = {
      ...layoutPositions,
      ...(options.workerPositions ?? {}),
    };

    const renderNodeIds = filtered.visibleNodeIds.filter((nodeId) => !hiddenNodeIds.has(nodeId));
    const visibleSet = new Set([...renderNodeIds, ...presentationNodes.map((node) => node.id)]);
    const highlightNodes = new Set(visualState.highlightedNodeIds);
    const highlightEdges = new Set(visualState.highlightedEdgeIds);
    const isIsolation = visualState.isolationActive && highlightNodes.size > 0;
    const labelMode = lodHints?.labelMode ?? LabelMode.ALL;
    const edgeOpacityFloor = lodHints?.edgeOpacityFloor ?? 0.4;
    const renderEdgeIds = lodHints?.visibleEdgeIds ?? filtered.visibleEdgeIds;

    if (this.sigma && lodHints) {
      this.sigma.setSetting('labelRenderedSizeThreshold', lodHints.labelRenderedSizeThreshold);
      this.sigma.setSetting('labelDensity', lodHints.labelDensity);
      this.sigma.setSetting('renderEdgeLabels', lodHints.renderEdgeLabels);
    }

    for (const nodeId of this.graph.nodes()) {
      if (!visibleSet.has(nodeId)) {
        if (this.graph.hasNode(nodeId)) {
          this.graph.dropNode(nodeId);
        }
      }
    }

    for (const nodeId of renderNodeIds) {
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
      const riskEmphasized = style.riskBand === 'high' || style.riskBand === 'critical';
      const interactionHighlighted = isSelected || isHovered || isHighlighted;
      const detailOverlay = labelMode === LabelMode.ALL;
      const anchorLabel = detailOverlay && (riskEmphasized || style.size >= 17);
      const riskSize = style.riskBand === 'critical' ? 3 : style.riskBand === 'high' ? 1.5 : 0;

      const attrs = {
        x: pos.x,
        y: pos.y,
        size: style.size + riskSize + (isSelected ? 4 : 0) + (isHovered ? 2 : 0),
        color: isDimmed ? `${style.color}33` : style.color,
        label: shouldRenderLabel(labelMode, isSelected, isHighlighted, isHovered)
          ? canonical.label
          : '',
        borderColor: style.borderColor,
        zIndex: isSelected ? 12 : isHovered ? 11 : isHighlighted ? 8 : riskEmphasized ? 4 : 0,
        type: 'circle',
        assetType: canonical.assetType,
        shape: NODE_SHAPES[canonical.assetType] ?? 'circle',
        riskBand: style.riskBand,
        riskColor: getRiskHaloColor(style.riskBand),
        selected: isSelected,
        hovered: isHovered,
        forceLabel: interactionHighlighted || anchorLabel,
        highlighted:
          interactionHighlighted ||
          detailOverlay ||
          (visualState.overlayToggles.risk && riskEmphasized),
        showHoverLabel: interactionHighlighted,
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

    for (const presentationNode of presentationNodes) {
      const memberPositions = presentationNode.memberIds
        .map((memberId) => positions[memberId])
        .filter((position): position is { x: number; y: number } => Boolean(position));
      const centroid =
        memberPositions.length > 0
          ? {
              x:
                memberPositions.reduce((sum, position) => sum + position.x, 0) /
                memberPositions.length,
              y:
                memberPositions.reduce((sum, position) => sum + position.y, 0) /
                memberPositions.length,
            }
          : { x: 0, y: 0 };

      const attrs = {
        x: centroid.x,
        y: centroid.y,
        size: 18 + Math.min(presentationNode.memberCount, 20),
        color: '#0f766e',
        label: `${presentationNode.label} (${String(presentationNode.memberCount)})`,
        borderColor: '#115e59',
        zIndex: 3,
        type: 'circle',
        assetType: 'cluster',
        shape: 'hexagon',
        forceLabel: true,
        highlighted: false,
        presentationClusterId: presentationNode.clusterId,
        riskHalo: 'transparent',
        statusIndicator: 'transparent',
      };

      if (this.graph.hasNode(presentationNode.id)) {
        this.graph.mergeNodeAttributes(presentationNode.id, attrs);
      } else {
        this.graph.addNode(presentationNode.id, attrs);
      }
    }

    const visibleEdgeSet = new Set(renderEdgeIds);
    for (const edgeId of this.graph.edges()) {
      const attrs = this.graph.getEdgeAttributes(edgeId);
      const key = attrs.key as string;
      if (!visibleEdgeSet.has(key)) {
        this.graph.dropEdge(edgeId);
      }
    }

    for (const edgeId of renderEdgeIds) {
      const canonical = entityMaps.edges.get(edgeId);
      if (!canonical) {
        continue;
      }
      if (
        hiddenNodeIds.has(canonical.source) ||
        hiddenNodeIds.has(canonical.target) ||
        !this.graph.hasNode(canonical.source) ||
        !this.graph.hasNode(canonical.target)
      ) {
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
        color: colorWithOpacity(
          isDimmed ? '#94a3b8' : isHighlighted ? highlightColor : edgeStyle.color,
          isDimmed
            ? DIMMED_OPACITY
            : isHighlighted
              ? 1
              : Math.max(edgeStyle.opacity, edgeOpacityFloor),
        ),
        type: edgeStyle.type,
        opacity: isDimmed
          ? DIMMED_OPACITY
          : isHighlighted
            ? 1
            : Math.max(edgeStyle.opacity, edgeOpacityFloor),
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
      visibleNodeIds: [...renderNodeIds, ...presentationNodes.map((node) => node.id)],
      visibleEdgeIds: renderEdgeIds,
      nodeCount: renderNodeIds.length + presentationNodes.length,
      edgeCount: renderEdgeIds.length,
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
        const result = store.getNeighborhood(selection.primaryNodeId, {
          hops: 1,
        });
        return {
          highlightedNodeIds: result.nodeIds,
          highlightedEdgeIds: result.edgeIds,
        };
      }
      case GraphHighlightMode.PATH: {
        if (!selection.secondaryNodeId) {
          return {
            highlightedNodeIds: [selection.primaryNodeId],
            highlightedEdgeIds: [],
          };
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
        const result = store.getIncidentSubgraph([selection.primaryNodeId], {
          hops: 2,
        });
        return {
          highlightedNodeIds: result.nodeIds,
          highlightedEdgeIds: result.edgeIds,
        };
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
