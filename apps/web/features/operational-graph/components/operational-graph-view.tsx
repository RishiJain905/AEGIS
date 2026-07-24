'use client';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { createGraphStore, GraphLayer, type GraphFilterSet } from '@aegis/graph-domain';
import {
  Badge,
  Button,
  GraphCameraControls,
  GraphIsolationControls,
  GraphLayerControls,
  GraphLegend,
  GraphOverlayToggle,
  GraphSearchInput,
  useReducedMotion,
} from '@aegis/ui';

import {
  GraphHighlightMode,
  LayoutStatus,
  type GraphVisualState,
} from '@/features/operational-graph/contracts/graph-visual-state';
import { useInvestigationDetail } from '@/features/investigation';
import { filterNodesBySearch } from '@/features/operational-graph/layout/initial-layout';
import {
  autoCollapseClusterIds,
  buildLodRenderHints,
  LayoutCoordinator,
  PerformanceInstrumentation,
  toggleCollapsedCluster,
  UpdateBatcher,
} from '@/features/operational-graph/performance';
import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import type { SigmaOperationalGraphAdapter } from '../adapters/sigma-operational-graph-adapter';
import { SigmaCanvas } from './sigma-canvas';

const LAYER_OPTIONS = [
  { id: GraphLayer.INFRASTRUCTURE, label: 'Infrastructure' },
  { id: GraphLayer.ACTIVITY, label: 'Activity' },
  { id: GraphLayer.SECURITY_STATE, label: 'Security' },
  { id: GraphLayer.INVESTIGATION, label: 'Investigation' },
  { id: GraphLayer.PRESENTATION, label: 'Presentation' },
];

type AccessibleGraphEntityListProps = {
  nodeIds: string[];
  nodeLabels: ReadonlyMap<string, string>;
  selectedEntityId: string | null;
  onNodeClick: (nodeId: string) => void;
};

const AccessibleGraphEntityList = memo(function AccessibleGraphEntityList({
  nodeIds,
  nodeLabels,
  selectedEntityId,
  onNodeClick,
}: AccessibleGraphEntityListProps) {
  const initialRenderCount = nodeIds.length > 1000 ? 50 : nodeIds.length;
  const [renderCount, setRenderCount] = useState(initialRenderCount);

  useEffect(() => {
    let cancelled = false;
    setRenderCount(initialRenderCount);
    if (initialRenderCount >= nodeIds.length) {
      return () => {
        cancelled = true;
      };
    }

    let timer: number | undefined;
    const appendNextChunk = () => {
      if (cancelled) {
        return;
      }
      setRenderCount((current) => {
        const next = Math.min(current + 250, nodeIds.length);
        if (next < nodeIds.length) {
          timer = window.requestAnimationFrame(appendNextChunk);
        }
        return next;
      });
    };
    timer = window.requestAnimationFrame(appendNextChunk);
    return () => {
      cancelled = true;
      if (timer !== undefined) {
        window.cancelAnimationFrame(timer);
      }
    };
  }, [initialRenderCount, nodeIds.length]);

  const renderedNodeIds = nodeIds.length > 1000 ? nodeIds.slice(0, renderCount) : nodeIds;

  return (
    <aside
      aria-label="Accessible graph entity list"
      data-testid="graph-entity-list"
      className="graph-entity-index max-h-44 overflow-auto rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] p-3"
    >
      <p className="mb-2 text-xs font-semibold text-[var(--aegis-text-muted)]">
        Nodes ({nodeIds.length}) · keyboard accessible list
      </p>
      <ul className="grid gap-1 sm:grid-cols-2 xl:grid-cols-3">
        {renderedNodeIds.map((nodeId) => (
          <li key={nodeId}>
            <button
              type="button"
              className="min-h-10 w-full rounded-[var(--aegis-radius-sm)] px-3 py-2 text-left text-xs text-[var(--aegis-text-secondary)] transition-[background-color,color,box-shadow] hover:bg-[var(--aegis-surface-elevated)] hover:text-[var(--aegis-text-primary)] aria-pressed:bg-[var(--aegis-accent-soft)] aria-pressed:text-[var(--aegis-text-primary)]"
              aria-pressed={selectedEntityId === nodeId}
              data-testid={`graph-entity-${nodeId}`}
              onClick={() => {
                onNodeClick(nodeId);
              }}
            >
              {nodeLabels.get(nodeId) ?? nodeId}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
});

const LEGEND_ITEMS = [
  { label: 'Service', color: '#36a9e1', shape: 'circle' as const },
  { label: 'Device', color: '#8999ff', shape: 'diamond' as const },
  { label: 'Database', color: '#efb85a', shape: 'square' as const },
  {
    label: 'Compromised',
    color: '#ff7078',
    shape: 'ring' as const,
    description: 'Attacker confirmed on asset',
  },
  {
    label: 'Suspicious',
    color: '#f1c257',
    shape: 'ring' as const,
    description: 'Anomalous signals, unconfirmed',
  },
  {
    label: 'Investigating',
    color: '#68d0ee',
    shape: 'ring' as const,
    description: 'Under active investigation',
  },
  {
    label: 'Contained',
    color: '#9aa8ff',
    shape: 'ring' as const,
    description: 'Isolated — dashed rim',
  },
  {
    label: 'High-risk link',
    color: '#ff9b55',
    shape: 'line' as const,
    description: 'Edge carrying attack-path risk',
  },
  {
    label: 'Evidence',
    color: '#fbbf24',
    shape: 'diamond' as const,
    description: 'Evidence-linked marker',
  },
];

export interface OperationalGraphViewProps {
  snapshot: GraphSnapshotV1;
  runId: string;
  incidentId?: string;
  graphStore?: import('@aegis/graph-domain').GraphStore;
  graphRevision?: number;
  /** Node ids with linked evidence (replay provides these); live runs have no
   * evidence projection yet, so the overlay stays empty there. */
  evidenceNodeIds?: string[];
  /** Node ids in incident scope; defaults to status-derived membership. */
  incidentNodeIds?: string[];
}

function useGraphStoreInstance(
  snapshot: GraphSnapshotV1,
  externalStore?: import('@aegis/graph-domain').GraphStore,
): import('@aegis/graph-domain').GraphStore {
  const internalStore = useMemo(() => {
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    return store;
  }, [snapshot.runId, snapshot.sequence, snapshot.revision]);
  return externalStore ?? internalStore;
}

function buildVisualStateWithPositions(
  visualState: GraphVisualState,
  positionsRef: React.RefObject<Record<string, { x: number; y: number }>>,
): GraphVisualState {
  return {
    ...visualState,
    nodePositions: { ...visualState.nodePositions, ...positionsRef.current },
  };
}

export function OperationalGraphView({
  snapshot,
  incidentId,
  graphStore,
  graphRevision = 0,
  evidenceNodeIds,
  incidentNodeIds,
}: OperationalGraphViewProps) {
  const store = useGraphStoreInstance(snapshot, graphStore);
  const investigationQuery = useInvestigationDetail(incidentId ?? '');
  const adapterRef = useRef<SigmaOperationalGraphAdapter | null>(null);
  const layoutCoordinatorRef = useRef<LayoutCoordinator | null>(null);
  const updateBatcherRef = useRef<UpdateBatcher | null>(null);
  const instrumentationRef = useRef<PerformanceInstrumentation | null>(null);
  const initialFitCompletedRef = useRef(false);
  const positionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const workerPositionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const [adapterReady, setAdapterReady] = useState(false);
  const [layoutStatus, setLayoutStatus] = useState<GraphVisualState['layoutStatus']>(
    LayoutStatus.IDLE,
  );
  const [lodTier, setLodTier] = useState('detail');
  const reducedMotion = useReducedMotion();

  const filterSet = useGraphVisualStore((s) => s.visualState.filterSet);
  const selection = useGraphVisualStore((s) => s.visualState.selection);
  const hoveredNodeId = useGraphVisualStore((s) => s.visualState.hoveredNodeId);
  const highlightMode = useGraphVisualStore((s) => s.visualState.highlightMode);
  const highlightedNodeIds = useGraphVisualStore((s) => s.visualState.highlightedNodeIds);
  const highlightedEdgeIds = useGraphVisualStore((s) => s.visualState.highlightedEdgeIds);
  const isolationActive = useGraphVisualStore((s) => s.visualState.isolationActive);
  const searchQuery = useGraphVisualStore((s) => s.visualState.searchQuery);
  const overlayToggles = useGraphVisualStore((s) => s.visualState.overlayToggles);
  const pathModeActive = useGraphVisualStore((s) => s.visualState.pathModeActive);
  const collapsedClusterIds = useGraphVisualStore((s) => s.visualState.collapsedClusterIds);

  const setSearchQuery = useGraphVisualStore((s) => s.setSearchQuery);
  const setFilterSet = useGraphVisualStore((s) => s.setFilterSet);
  const setHoveredNodeId = useGraphVisualStore((s) => s.setHoveredNodeId);
  const setHighlight = useGraphVisualStore((s) => s.setHighlight);
  const clearHighlight = useGraphVisualStore((s) => s.clearHighlight);
  const setPathModeActive = useGraphVisualStore((s) => s.setPathModeActive);
  const toggleOverlay = useGraphVisualStore((s) => s.toggleOverlay);
  const setCollapsedClusterIds = useGraphVisualStore((s) => s.setCollapsedClusterIds);
  const mergeNodePositions = useGraphVisualStore((s) => s.mergeNodePositions);
  const setLayoutStatusInStore = useGraphVisualStore((s) => s.setLayoutStatus);

  const setSelectedEntityId = useWorkspaceUiStore((s) => s.setSelectedEntityId);
  const selectedEntityId = useWorkspaceUiStore((s) => s.workspace.selectedEntityId);

  const nodeLabels = useMemo(() => {
    const map = new Map<string, string>();
    for (const node of snapshot.nodes) {
      map.set(node.id, node.label);
    }
    return map;
  }, [snapshot.nodes]);

  const evidenceSet = useMemo(() => new Set(evidenceNodeIds ?? []), [evidenceNodeIds]);
  // Without an explicit incident projection, approximate incident scope from
  // node security status — the same derivation replay uses.
  const incidentSet = useMemo(() => {
    if (incidentNodeIds) {
      return new Set(incidentNodeIds);
    }
    return new Set(
      snapshot.nodes
        .filter(
          (node) =>
            node.status === 'under_investigation' ||
            node.status === 'compromised' ||
            node.status === 'contained',
        )
        .map((node) => node.id),
    );
  }, [incidentNodeIds, snapshot.nodes]);
  const evidenceSetRef = useRef(evidenceSet);
  evidenceSetRef.current = evidenceSet;
  const incidentSetRef = useRef(incidentSet);
  incidentSetRef.current = incidentSet;

  const runSync = useCallback(() => {
    const adapter = adapterRef.current;
    if (!adapter) {
      return;
    }
    const syncStartedAt = performance.now();
    const state = buildVisualStateWithPositions(
      useGraphVisualStore.getState().visualState,
      positionsRef,
    );
    const filtered = store.applyFilters(state.filterSet as GraphFilterSet);
    const autoCollapsed = autoCollapseClusterIds(
      store.exportSnapshot().nodes.filter((node) => filtered.visibleNodeIds.includes(node.id)),
      buildLodRenderHints({
        visibleNodeIds: filtered.visibleNodeIds,
        visibleEdgeIds: filtered.visibleEdgeIds,
        highlightedEdgeIds: state.highlightedEdgeIds,
        collapsedClusterIds: state.collapsedClusterIds,
      }).clusterCollapseThreshold,
    );
    const effectiveCollapsed = [...new Set([...state.collapsedClusterIds, ...autoCollapsed])];
    const lodHints = buildLodRenderHints({
      visibleNodeIds: filtered.visibleNodeIds,
      visibleEdgeIds: filtered.visibleEdgeIds,
      highlightedEdgeIds: state.highlightedEdgeIds,
      collapsedClusterIds: effectiveCollapsed,
    });
    setLodTier(lodHints.tierId);

    const projection = adapter.syncFromStore(
      store,
      state.filterSet as GraphFilterSet,
      { ...state, collapsedClusterIds: effectiveCollapsed },
      {
        lodHints,
        workerPositions: workerPositionsRef.current,
        evidenceNodeIds: evidenceSetRef.current,
        incidentNodeIds: incidentSetRef.current,
      },
    );
    for (const id of projection.visibleNodeIds) {
      const attrs = adapter.getPresentationGraph().getNodeAttributes(id);
      positionsRef.current[id] = { x: attrs.x as number, y: attrs.y as number };
    }

    if (!initialFitCompletedRef.current) {
      initialFitCompletedRef.current = true;
      requestAnimationFrame(() => {
        adapter.fitGraph();
      });
    }

    const instrumentation = instrumentationRef.current;
    instrumentation?.recordSample({
      frameTimeMs: performance.now() - syncStartedAt,
      syncLatencyMs: performance.now() - syncStartedAt,
      workerDurationMs: layoutCoordinatorRef.current?.getWorkerDurationMs() ?? null,
      visibleNodes: projection.nodeCount,
      visibleEdges: projection.edgeCount,
      lodTier: lodHints.tierId,
      droppedFrames: updateBatcherRef.current?.getDroppedFrames() ?? 0,
      droppedWorkerResults: instrumentation.getDroppedWorkerResults(),
    });
  }, [store]);

  const scheduleSync = useCallback(() => {
    if (!updateBatcherRef.current) {
      updateBatcherRef.current = new UpdateBatcher({
        onOverBudget: () => {
          instrumentationRef.current?.recordDroppedFrame();
        },
      });
    }
    updateBatcherRef.current.schedule(runSync);
  }, [runSync]);

  const scheduleLayout = useCallback(() => {
    const coordinator = layoutCoordinatorRef.current;
    if (!coordinator) {
      return;
    }
    const state = useGraphVisualStore.getState().visualState;
    coordinator.scheduleLayout(store, state.filterSet as GraphFilterSet, state.pinnedNodeIds);
  }, [store]);

  useEffect(() => {
    if (adapterReady) {
      scheduleSync();
      scheduleLayout();
    }
  }, [
    adapterReady,
    scheduleSync,
    scheduleLayout,
    filterSet,
    selection,
    hoveredNodeId,
    highlightMode,
    highlightedNodeIds,
    highlightedEdgeIds,
    isolationActive,
    overlayToggles,
    collapsedClusterIds,
    snapshot.revision,
    snapshot.sequence,
    graphRevision,
    evidenceSet,
    incidentSet,
  ]);

  useEffect(() => {
    if (!pathModeActive || !selection.primaryNodeId || !selection.secondaryNodeId) {
      return;
    }
    const adapter = adapterRef.current;
    if (!adapter) {
      return;
    }
    const state = buildVisualStateWithPositions(
      useGraphVisualStore.getState().visualState,
      positionsRef,
    );
    const highlight = adapter.applyHighlight(store, {
      ...state,
      highlightMode: GraphHighlightMode.PATH,
    });
    setHighlight(
      GraphHighlightMode.PATH,
      highlight.highlightedNodeIds,
      highlight.highlightedEdgeIds,
      false,
    );
  }, [pathModeActive, selection.primaryNodeId, selection.secondaryNodeId, store, setHighlight]);

  useEffect(() => {
    if (!incidentId || !investigationQuery.data) {
      return;
    }
    const state = useGraphVisualStore.getState().visualState;
    const investigationLayerEnabled = state.filterSet.enabledLayers.includes(
      GraphLayer.INVESTIGATION,
    );
    if (!investigationLayerEnabled || !state.overlayToggles.incident) {
      return;
    }
    if (
      state.highlightMode !== GraphHighlightMode.NONE &&
      state.highlightMode !== GraphHighlightMode.INCIDENT
    ) {
      return;
    }

    const latestOverlay = investigationQuery.data.overlays.at(-1);
    if (!latestOverlay) {
      return;
    }

    const nodeIds = latestOverlay.highlights
      .filter((highlight) => highlight.entityType === 'asset')
      .map((highlight) => highlight.entityId);
    const edgeIds = latestOverlay.edgeHighlights.map((highlight) => highlight.entityId);

    if (nodeIds.length === 0 && edgeIds.length === 0) {
      return;
    }

    setHighlight(GraphHighlightMode.INCIDENT, nodeIds, edgeIds, false);
  }, [
    incidentId,
    investigationQuery.data,
    filterSet.enabledLayers,
    overlayToggles.incident,
    highlightMode,
    setHighlight,
  ]);

  const handleAdapterReady = useCallback(
    (adapter: SigmaOperationalGraphAdapter) => {
      adapterRef.current = adapter;
      instrumentationRef.current = new PerformanceInstrumentation();
      layoutCoordinatorRef.current = new LayoutCoordinator({
        instrumentation: instrumentationRef.current,
        onPositionsUpdated: (positions) => {
          // Positions arrive pre-shaped by the zone sector layout; no aspect
          // correction — stretching would tear nodes out of their zone frames.
          workerPositionsRef.current = positions;
          mergeNodePositions(positions);
          scheduleSync();
        },
        onLayoutStatusChanged: (status) => {
          setLayoutStatus(status);
          setLayoutStatusInStore(status);
        },
      });
      const coordinator = layoutCoordinatorRef.current;
      void coordinator
        .initialize()
        .then(() => {
          if (layoutCoordinatorRef.current !== coordinator) {
            return;
          }
          setAdapterReady(true);
          scheduleLayout();
        })
        .catch(() => {
          if (layoutCoordinatorRef.current !== coordinator) {
            return;
          }
          setLayoutStatus(LayoutStatus.ERROR);
          setLayoutStatusInStore(LayoutStatus.ERROR);
          setAdapterReady(true);
        });
    },
    [mergeNodePositions, scheduleLayout, scheduleSync, setLayoutStatusInStore],
  );

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      const presentationGraph = adapterRef.current?.getPresentationGraph();
      const presentationClusterId = presentationGraph?.hasNode(nodeId)
        ? (presentationGraph.getNodeAttribute(nodeId, 'presentationClusterId') as
            | string
            | undefined)
        : undefined;

      if (presentationClusterId) {
        setCollapsedClusterIds(toggleCollapsedCluster(collapsedClusterIds, presentationClusterId));
        return;
      }

      setSelectedEntityId(nodeId);

      if (pathModeActive) {
        const current = useGraphVisualStore.getState().visualState.selection;
        if (current.primaryNodeId && current.primaryNodeId !== nodeId) {
          useGraphVisualStore.getState().setSelection(current.primaryNodeId, nodeId);
        } else {
          useGraphVisualStore.getState().setSelection(nodeId, null);
        }
      } else {
        useGraphVisualStore.getState().setSelection(nodeId, null);
      }

      adapterRef.current?.focusNode(nodeId);
    },
    [setSelectedEntityId, pathModeActive, collapsedClusterIds, setCollapsedClusterIds],
  );

  useEffect(() => {
    return () => {
      layoutCoordinatorRef.current?.dispose();
      layoutCoordinatorRef.current = null;
      updateBatcherRef.current?.dispose();
      updateBatcherRef.current = null;
      instrumentationRef.current = null;
      workerPositionsRef.current = {};
      initialFitCompletedRef.current = false;
    };
  }, [snapshot.runId]);

  const handleIsolate = useCallback(() => {
    const primaryId = selection.primaryNodeId ?? selectedEntityId;
    if (!primaryId) {
      return;
    }
    const adapter = adapterRef.current;
    if (!adapter) {
      return;
    }
    const state = buildVisualStateWithPositions(
      useGraphVisualStore.getState().visualState,
      positionsRef,
    );
    const highlight = adapter.applyHighlight(store, {
      ...state,
      highlightMode: GraphHighlightMode.NEIGHBORHOOD,
      selection: { ...state.selection, primaryNodeId: primaryId },
    });
    setHighlight(
      GraphHighlightMode.NEIGHBORHOOD,
      highlight.highlightedNodeIds,
      highlight.highlightedEdgeIds,
      true,
    );
  }, [selection.primaryNodeId, selectedEntityId, store, setHighlight]);

  const handleRestore = useCallback(() => {
    clearHighlight();
  }, [clearHighlight]);

  const handleLayerToggle = useCallback(
    (layerId: string) => {
      const current = filterSet.enabledLayers;
      const enabled = current.includes(layerId)
        ? current.filter((l) => l !== layerId)
        : [...current, layerId];
      if (enabled.length === 0) {
        return;
      }
      setFilterSet({
        ...filterSet,
        enabledLayers: enabled as GraphFilterSet['enabledLayers'],
      });
    },
    [filterSet, setFilterSet],
  );

  useEffect(() => {
    if (layoutStatus === LayoutStatus.COMPLETE) {
      adapterRef.current?.fitGraph();
    }
  }, [layoutStatus]);

  const filteredNodeIds = useMemo(() => {
    const exported = store.exportSnapshot();
    const allIds = exported.nodes.map((n) => n.id);
    return filterNodesBySearch(allIds, nodeLabels, searchQuery);
  }, [store, nodeLabels, searchQuery]);

  return (
    <div
      className="flex min-h-[28rem] flex-col gap-3"
      data-testid="operational-graph-view"
      data-layout-status={layoutStatus}
      data-lod-tier={lodTier}
      data-node-count={filteredNodeIds.length}
    >
      <div className="graph-command-bar flex flex-col gap-3 lg:flex-row lg:items-center">
        <GraphSearchInput value={searchQuery} onChange={setSearchQuery} className="lg:max-w-sm" />
        <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
          <Badge variant="outline" className="font-mono uppercase tracking-[0.12em]">
            {layoutStatus}
          </Badge>
          <span className="font-mono text-[11px] text-[var(--aegis-text-muted)]">
            {String(filteredNodeIds.length)} nodes · LOD {lodTier}
          </span>
        </div>
        <GraphCameraControls
          onFit={() => adapterRef.current?.fitGraph()}
          onZoomIn={() => adapterRef.current?.zoomIn()}
          onZoomOut={() => adapterRef.current?.zoomOut()}
          onReset={() => adapterRef.current?.resetCamera()}
        />
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="graph-control-deck grid gap-x-5 gap-y-2.5 lg:grid-cols-2">
          <div>
            <p className="graph-control-label">Data layers</p>
            <GraphLayerControls
              layers={LAYER_OPTIONS}
              enabledLayers={filterSet.enabledLayers}
              onToggle={handleLayerToggle}
            />
          </div>
          <div>
            <p className="graph-control-label">Signal overlays</p>
            <GraphOverlayToggle toggles={overlayToggles} onToggle={toggleOverlay} />
          </div>
          <div>
            <p className="graph-control-label">Investigation focus</p>
            <GraphIsolationControls
              isolationActive={isolationActive}
              onIsolate={handleIsolate}
              onRestore={handleRestore}
              disabled={!selection.primaryNodeId && !selectedEntityId}
            />
          </div>
          <div>
            <p className="graph-control-label">Analysis actions</p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={pathModeActive ? 'default' : 'outline'}
                size="sm"
                data-testid="graph-path-mode"
                aria-pressed={pathModeActive}
                onClick={() => {
                  setPathModeActive(!pathModeActive);
                }}
                className="text-xs"
              >
                {pathModeActive ? 'Path mode (select 2 nodes)' : 'Trace path'}
              </Button>
              <Button
                variant={collapsedClusterIds.length > 0 ? 'default' : 'outline'}
                size="sm"
                data-testid="graph-collapse-clusters"
                aria-pressed={collapsedClusterIds.length > 0}
                onClick={() => {
                  if (collapsedClusterIds.length > 0) {
                    setCollapsedClusterIds([]);
                    return;
                  }
                  const filtered = store.applyFilters(
                    useGraphVisualStore.getState().visualState.filterSet as GraphFilterSet,
                  );
                  const autoCollapsed = autoCollapseClusterIds(
                    store
                      .exportSnapshot()
                      .nodes.filter((node) => filtered.visibleNodeIds.includes(node.id)),
                    3,
                  );
                  setCollapsedClusterIds(autoCollapsed);
                }}
                className="text-xs"
              >
                {collapsedClusterIds.length > 0
                  ? 'Expand collapsed clusters'
                  : 'Collapse dense clusters'}
              </Button>
            </div>
          </div>
        </div>
        <GraphLegend items={LEGEND_ITEMS} />
      </div>

      <div
        className="operational-graph-frame relative min-h-[28rem] flex-1 overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-base)]"
        data-reduced-motion={reducedMotion ? 'true' : 'false'}
      >
        <div
          className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-2"
          aria-hidden="true"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--aegis-accent-cyan)] shadow-[0_0_10px_var(--aegis-accent-cyan)]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--aegis-text-muted)]">
            Analysis plane · drag to pan · scroll to zoom
          </span>
        </div>
        <SigmaCanvas
          className="absolute inset-0"
          onAdapterReady={handleAdapterReady}
          onNodeClick={handleNodeClick}
          onStageClick={() => {
            setSelectedEntityId(null);
            useGraphVisualStore.getState().setSelection(null, null);
          }}
          onNodeHover={setHoveredNodeId}
        />
      </div>

      <AccessibleGraphEntityList
        nodeIds={filteredNodeIds}
        nodeLabels={nodeLabels}
        selectedEntityId={selectedEntityId}
        onNodeClick={handleNodeClick}
      />
    </div>
  );
}
