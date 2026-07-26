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
import { computeHighlight } from '../semantic/graph-highlights';
import { computeLayerEmphasis } from '../semantic/layer-emphasis';
import {
  getEdgeVisualStyle,
  getNodeShape,
  getNodeVisualStyle,
  getRiskHaloColor,
  resolveEdgeFlowStyle,
  resolveEdgeSemanticStyle,
  type EdgeFlowProfile,
  type EdgeHighlightKind,
} from '../semantic/graph-semantic-styles';
import { EdgeActivityTracker, edgeFlowPhase } from '../semantic/edge-activity';
import { detectRevealTransitions, type NodeRevealState } from '../semantic/reveal-detection';
import { zoneLabelFromClusterId, UNZONED_CLUSTER_ID } from '../layout/zone-layout';
import { drawAegisNodeHover } from '../rendering/aegis-canvas-renderers';
import { rollupZoneThreat, ZoneOverlay, type ZoneRenderState } from '../rendering/zone-overlay';
import { SignalOverlay, type NodeSignal, type SignalStatus } from '../rendering/signal-overlay';
import { LabelTopcoat } from '../rendering/label-topcoat';
import {
  AliveEdgeArrowProgram,
  AliveEdgeLineProgram,
  setAliveEdgeFlowProfile,
} from '../rendering/alive-edge-program';

const DIMMED_OPACITY = 0.15;

function highlightKindForMode(
  mode: (typeof GraphHighlightMode)[keyof typeof GraphHighlightMode],
): EdgeHighlightKind | null {
  switch (mode) {
    case GraphHighlightMode.NEIGHBORHOOD:
      return 'neighborhood';
    case GraphHighlightMode.PATH:
      return 'path';
    case GraphHighlightMode.INCIDENT:
      return 'incident';
    case GraphHighlightMode.DEPENDENCIES:
      return 'dependencies';
    case GraphHighlightMode.NONE:
      return null;
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Unhandled highlight mode: ${String(_exhaustive)}`);
    }
  }
}

// Sigma's WebGL node/edge programs render colors opaquely — alpha channels in
// `#RRGGBBAA`/`rgba()` values are ignored. To make dimming actually visible we
// pre-composite against the canvas background and emit a solid hex.
const CANVAS_BACKGROUND = { red: 10, green: 17, blue: 24 };

function colorWithOpacity(color: string, opacity: number): string {
  const match = color.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!match) {
    return color;
  }
  const [, red = '00', green = '00', blue = '00'] = match;
  const alpha = Math.min(1, Math.max(0, opacity));
  const blend = (channel: string, background: number) =>
    Math.round(background + (Number.parseInt(channel, 16) - background) * alpha)
      .toString(16)
      .padStart(2, '0');
  return `#${blend(red, CANVAS_BACKGROUND.red)}${blend(green, CANVAS_BACKGROUND.green)}${blend(blue, CANVAS_BACKGROUND.blue)}`;
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
  private readonly edgeActivity = new EdgeActivityTracker();
  private flowProfile: EdgeFlowProfile = 'static';
  private flowFrameHandle: number | null = null;
  private zoneOverlay: ZoneOverlay | null = null;
  private signalOverlay: SignalOverlay | null = null;
  private labelTopcoat: LabelTopcoat | null = null;
  private revealState: Map<string, NodeRevealState> | null = null;
  private lastRevealedNodeIds: string[] = [];

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
      // The container can legitimately be mid-layout (mode toggle, panel
      // remount); mounting must never throw — a ResizeObserver in SigmaCanvas
      // resizes the renderer as soon as real dimensions arrive.
      allowInvalidContainer: true,
      defaultNodeColor: '#8b8e96',
      defaultEdgeColor: '#55555f',
      labelFont: '"JetBrains Mono", "Cascadia Mono", "Segoe UI", sans-serif',
      labelSize: 12,
      labelWeight: '600',
      labelColor: { color: '#cdced4' },
      labelRenderedSizeThreshold: 9,
      labelDensity: 0.72,
      // Wide enough for the pill-style labels (marker + full asset name) to
      // pick non-overlapping cells in dense zone sectors; the stock Sigma
      // default (100) was sized for short plain-text labels, not these.
      labelGridCellSize: 190,
      stagePadding: 52,
      hideLabelsOnMove: false,
      hideEdgesOnMove: false,
      // Sigma's own 'labels' canvas still decides *which* nodes get a label
      // (density/grid/forceLabel selection — read via getNodeDisplayedLabels),
      // but paints nothing: LabelTopcoat is the sole label painter, so every
      // label goes through the same collision-aware, edge-aware placement in
      // one pass instead of Sigma drawing an uncollided version underneath
      // that would show through whenever the topcoat skips a lower-priority
      // label for overlapping a higher-priority one.
      defaultDrawNodeLabel: () => undefined,
      defaultDrawNodeHover: drawAegisNodeHover,
      minEdgeThickness: 0.75,
      minCameraRatio: 0.06,
      maxCameraRatio: 6,
      zIndex: true,
      // Alive-edge programs (§7.9): same visual contract as the stock
      // line/arrow programs plus dash + shared-clock flow support.
      edgeProgramClasses: {
        line: AliveEdgeLineProgram,
        arrow: AliveEdgeArrowProgram,
      },
    });
    // Overlay layers (zone hulls under edges, status/reveal signals under
    // nodes, label topcoat above everything). Guarded so renderer test
    // doubles without the layer API still exercise the adapter's
    // projection logic.
    if (typeof this.sigma.createCanvas === 'function') {
      this.zoneOverlay = new ZoneOverlay(this.sigma, this.graph);
      this.signalOverlay = new SignalOverlay(this.sigma, this.graph, this.reducedMotion);
      this.labelTopcoat = new LabelTopcoat(this.sigma);
    }
    this.syncFlowDriver();
    return this.sigma;
  }

  setReducedMotion(reduced: boolean): void {
    this.reducedMotion = reduced;
    this.signalOverlay?.setReducedMotion(reduced);
  }

  /**
   * §7.9 gate for the 2D renderer. 'static' (reduced motion or LOW tier)
   * freezes the shader clock and stops the render driver entirely; 'coarse'
   * (MEDIUM) keeps the loop but collapses per-edge phases in the shader.
   */
  setEdgeFlowProfile(profile: EdgeFlowProfile): void {
    if (this.flowProfile === profile) {
      return;
    }
    this.flowProfile = profile;
    setAliveEdgeFlowProfile(profile);
    this.syncFlowDriver();
    // One render so a profile change (e.g. reduced-motion toggle) takes
    // effect immediately even when the loop is now stopped.
    this.sigma?.scheduleRender();
  }

  /** rAF loop that only schedules WebGL re-renders — Sigma re-reads the shared
   * clock via uniforms; no data reprocessing, no allocation per frame. */
  private syncFlowDriver(): void {
    const shouldRun = this.sigma !== null && this.flowProfile !== 'static';
    if (!shouldRun) {
      if (this.flowFrameHandle !== null) {
        cancelAnimationFrame(this.flowFrameHandle);
        this.flowFrameHandle = null;
      }
      return;
    }
    if (this.flowFrameHandle !== null) {
      return;
    }
    const step = () => {
      if (this.sigma === null || this.flowProfile === 'static') {
        this.flowFrameHandle = null;
        return;
      }
      this.sigma.scheduleRender();
      this.flowFrameHandle = requestAnimationFrame(step);
    };
    this.flowFrameHandle = requestAnimationFrame(step);
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
    const emphasis = computeLayerEmphasis(
      { nodes: snapshot.nodes, edges: snapshot.edges },
      filterSet.enabledLayers,
    );
    const evidenceNodeIds = options.evidenceNodeIds ?? new Set<string>();
    const incidentNodeIds = options.incidentNodeIds ?? new Set<string>();
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
      const isHovered = visualState.hoveredNodeId === nodeId;
      const isSelected = visualState.selection.primaryNodeId === nodeId;
      const isLayerDimmed = emphasis.dimmedNodeIds.has(nodeId) && !isHighlighted && !isSelected;
      const isDimmed = (isIsolation && !isHighlighted) || isLayerDimmed;
      const riskEmphasized = style.riskBand === 'high' || style.riskBand === 'critical';
      const interactionHighlighted = isSelected || isHovered || isHighlighted;
      const detailOverlay = labelMode === LabelMode.ALL;
      const anchorLabel = detailOverlay && (riskEmphasized || style.size >= 17);
      const riskSize = style.riskBand === 'critical' ? 3 : style.riskBand === 'high' ? 1.5 : 0;

      const attrs = {
        x: pos.x,
        y: pos.y,
        size: style.size + riskSize + (isSelected ? 4 : 0) + (isHovered ? 2 : 0),
        color: isDimmed ? colorWithOpacity(style.color, 0.22) : style.color,
        label:
          !isDimmed && shouldRenderLabel(labelMode, isSelected, isHighlighted, isHovered)
            ? canonical.label
            : '',
        borderColor: style.borderColor,
        zIndex: isSelected ? 12 : isHovered ? 11 : isHighlighted ? 8 : riskEmphasized ? 4 : 0,
        type: 'circle',
        assetType: canonical.assetType,
        shape: getNodeShape(canonical.assetType),
        riskBand: style.riskBand,
        riskColor: getRiskHaloColor(style.riskBand),
        selected: isSelected,
        hovered: isHovered,
        forceLabel: !isDimmed && (interactionHighlighted || anchorLabel),
        highlighted:
          interactionHighlighted ||
          (!isDimmed && (detailOverlay || (visualState.overlayToggles.risk && riskEmphasized))),
        showHoverLabel: interactionHighlighted,
        riskHalo:
          visualState.overlayToggles.risk && !isDimmed
            ? getRiskHaloColor(style.riskBand)
            : 'transparent',
        statusIndicator:
          visualState.overlayToggles.status && !isDimmed ? style.statusColor : 'transparent',
        evidenceMarked:
          visualState.overlayToggles.evidence && !isDimmed && evidenceNodeIds.has(nodeId),
        incidentMarked:
          visualState.overlayToggles.incident && !isDimmed && incidentNodeIds.has(nodeId),
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
        evidenceMarked: false,
        incidentMarked: false,
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

    // Pulse detection runs on the same sync tick the GraphStore delta landed
    // on — a live event traversing a relationship lights that edge up now.
    this.edgeActivity.update(snapshot.edges);
    const highlightKind = highlightKindForMode(visualState.highlightMode);

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
      const isDimmed = (isIsolation || emphasis.dimmedEdgeIds.has(edgeId)) && !isHighlighted;
      const semantic = resolveEdgeSemanticStyle({
        edge: canonical,
        highlighted: isHighlighted,
        dimmed: isDimmed,
        highlightKind,
      });
      const flow = resolveEdgeFlowStyle({
        directed: canonical.directed,
        highlighted: isHighlighted,
        dimmed: isDimmed,
      });
      const opacity = isDimmed
        ? DIMMED_OPACITY
        : isHighlighted
          ? 1
          : Math.max(semantic.opacity, edgeOpacityFloor);

      const attrs = {
        key: edgeId,
        size: semantic.width,
        color: colorWithOpacity(semantic.color, opacity),
        type: edgeStyle.type,
        opacity,
        zIndex: isHighlighted ? 1 : 0,
        // Alive-edge attributes (§7.4 dash + §7.9 flow), consumed by the
        // custom edge programs in rendering/alive-edge-program.ts.
        dashFlag: semantic.dashed ? 1 : 0,
        flowSpeed: flow?.speed ?? 0,
        flowAmplitude: flow?.amplitude ?? 0,
        pulseAt: this.edgeActivity.getPulseAt(edgeId),
        flowPhase: edgeFlowPhase(edgeId),
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

    this.updateOverlays(snapshot, renderNodeIds);

    this.sigma?.refresh();

    return {
      visibleNodeIds: [...renderNodeIds, ...presentationNodes.map((node) => node.id)],
      visibleEdgeIds: renderEdgeIds,
      nodeCount: renderNodeIds.length + presentationNodes.length,
      edgeCount: renderEdgeIds.length,
    };
  }

  /** Zone frames, status halos, and the reveal pulse — all derived from the
   * same canonical snapshot the node projection used this sync tick. */
  private updateOverlays(snapshot: GraphSnapshotV1, renderNodeIds: string[]): void {
    const renderSet = new Set(renderNodeIds);

    const { revealedNodeIds, nextState } = detectRevealTransitions(
      this.revealState,
      snapshot.nodes,
    );
    this.revealState = nextState;
    this.lastRevealedNodeIds = revealedNodeIds.filter((nodeId) => renderSet.has(nodeId));

    if (!this.zoneOverlay && !this.signalOverlay) {
      return;
    }

    const clusterLabels = new Map(snapshot.clusters.map((cluster) => [cluster.id, cluster.label]));
    const zoneMembers = new Map<string, { memberIds: string[]; statuses: string[] }>();
    const signals: NodeSignal[] = [];

    for (const node of snapshot.nodes) {
      if (!renderSet.has(node.id)) {
        continue;
      }
      const zoneId = node.clusterId ?? UNZONED_CLUSTER_ID;
      const zone = zoneMembers.get(zoneId) ?? { memberIds: [], statuses: [] };
      zone.memberIds.push(node.id);
      zone.statuses.push(node.status);
      zoneMembers.set(zoneId, zone);

      if (node.status !== 'normal' && node.disclosed !== false) {
        signals.push({ id: node.id, status: node.status as SignalStatus });
      }
    }

    const zones: ZoneRenderState[] = [...zoneMembers.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([zoneId, zone]) => ({
        id: zoneId,
        label: clusterLabels.get(zoneId) ?? zoneLabelFromClusterId(zoneId),
        memberIds: zone.memberIds,
        threat: rollupZoneThreat(zone.statuses),
      }));

    this.zoneOverlay?.setZones(zones);
    this.signalOverlay?.setSignals(signals);
    if (this.lastRevealedNodeIds.length > 0) {
      this.signalOverlay?.addReveals(this.lastRevealedNodeIds);
    }
  }

  /** Node ids whose fog-of-war reveal fired on the most recent sync. */
  getLastRevealedNodeIds(): string[] {
    return [...this.lastRevealedNodeIds];
  }

  applyHighlight(
    store: GraphStore,
    visualState: GraphVisualState,
  ): { highlightedNodeIds: string[]; highlightedEdgeIds: string[] } {
    return computeHighlight(store, visualState);
  }

  focusNode(nodeId: string): void {
    if (!this.sigma || !this.graph.hasNode(nodeId)) {
      return;
    }
    const camera = this.sigma.getCamera();
    const displayData = this.sigma.getNodeDisplayData(nodeId);
    if (!displayData) {
      return;
    }
    // Centre the node without yanking the zoom level: keep the operator's
    // current ratio unless they are zoomed far out, in which case ease in just
    // enough for the neighborhood to be readable.
    void camera.animate(
      { x: displayData.x, y: displayData.y, ratio: Math.min(camera.ratio, 0.55) },
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

  resize(): void {
    if (!this.sigma) {
      return;
    }
    this.sigma.resize();
    this.sigma.refresh();
  }

  dispose(): void {
    if (this.flowFrameHandle !== null) {
      cancelAnimationFrame(this.flowFrameHandle);
      this.flowFrameHandle = null;
    }
    this.zoneOverlay?.dispose();
    this.zoneOverlay = null;
    this.signalOverlay?.dispose();
    this.signalOverlay = null;
    this.labelTopcoat?.dispose();
    this.labelTopcoat = null;
    this.revealState = null;
    this.lastRevealedNodeIds = [];
    if (this.sigma) {
      this.sigma.kill();
      this.sigma = null;
    }
    this.graph.clear();
    this.edgeActivity.clear();
  }
}

export function createSigmaOperationalGraphAdapter(
  container: HTMLElement,
  reducedMotion = false,
): SigmaOperationalGraphAdapter {
  return new SigmaOperationalGraphAdapter(container, reducedMotion);
}
