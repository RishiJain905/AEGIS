'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { createGraphStore, GraphLayer, type GraphFilterSet } from '@aegis/graph-domain';
import {
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

const LEGEND_ITEMS = [
  { label: 'Service', color: '#3b82f6' },
  { label: 'Device', color: '#8b5cf6' },
  { label: 'Database', color: '#f59e0b' },
  { label: 'High risk path', color: '#f59e0b' },
  { label: 'Neighborhood', color: '#3b82f6' },
];

export interface OperationalGraphViewProps {
  snapshot: GraphSnapshotV1;
  runId: string;
}

function useGraphStoreInstance(
  snapshot: GraphSnapshotV1,
): import('@aegis/graph-domain').GraphStore {
  return useMemo(() => {
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    return store;
  }, [snapshot.runId, snapshot.sequence, snapshot.revision]);
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

export function OperationalGraphView({ snapshot }: OperationalGraphViewProps) {
  const store = useGraphStoreInstance(snapshot);
  const adapterRef = useRef<SigmaOperationalGraphAdapter | null>(null);
  const layoutCoordinatorRef = useRef<LayoutCoordinator | null>(null);
  const updateBatcherRef = useRef<UpdateBatcher | null>(null);
  const instrumentationRef = useRef<PerformanceInstrumentation | null>(null);
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
      },
    );
    for (const id of projection.visibleNodeIds) {
      const attrs = adapter.getPresentationGraph().getNodeAttributes(id);
      positionsRef.current[id] = { x: attrs.x as number, y: attrs.y as number };
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

  const handleAdapterReady = useCallback(
    (adapter: SigmaOperationalGraphAdapter) => {
      adapterRef.current = adapter;
      instrumentationRef.current = new PerformanceInstrumentation();
      layoutCoordinatorRef.current = new LayoutCoordinator({
        instrumentation: instrumentationRef.current,
        onPositionsUpdated: (positions) => {
          workerPositionsRef.current = positions;
          mergeNodePositions(positions);
          scheduleSync();
        },
        onLayoutStatusChanged: (status) => {
          setLayoutStatus(status);
          setLayoutStatusInStore(status);
        },
      });
      void layoutCoordinatorRef.current.initialize().then(() => {
        setAdapterReady(true);
        scheduleLayout();
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
      className="flex min-h-[20rem] flex-col gap-3"
      data-testid="operational-graph-view"
      data-layout-status={layoutStatus}
      data-lod-tier={lodTier}
    >
      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <GraphSearchInput value={searchQuery} onChange={setSearchQuery} className="max-w-xs" />
        <GraphCameraControls
          onFit={() => adapterRef.current?.fitGraph()}
          onZoomIn={() => adapterRef.current?.zoomIn()}
          onZoomOut={() => adapterRef.current?.zoomOut()}
          onReset={() => adapterRef.current?.resetCamera()}
        />
      </div>

      <div className="flex flex-col gap-2 xl:flex-row xl:items-start">
        <div className="flex flex-1 flex-col gap-2">
          <GraphLayerControls
            layers={LAYER_OPTIONS}
            enabledLayers={filterSet.enabledLayers}
            onToggle={handleLayerToggle}
          />
          <GraphOverlayToggle toggles={overlayToggles} onToggle={toggleOverlay} />
          <GraphIsolationControls
            isolationActive={isolationActive}
            onIsolate={handleIsolate}
            onRestore={handleRestore}
            disabled={!selection.primaryNodeId && !selectedEntityId}
          />
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-default)] px-3 py-1 text-xs hover:bg-[var(--aegis-surface-elevated)]"
              data-testid="graph-path-mode"
              aria-pressed={pathModeActive}
              onClick={() => {
                setPathModeActive(!pathModeActive);
              }}
            >
              {pathModeActive ? 'Path mode (select 2 nodes)' : 'Trace path'}
            </button>
            <button
              type="button"
              className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-default)] px-3 py-1 text-xs hover:bg-[var(--aegis-surface-elevated)]"
              data-testid="graph-collapse-clusters"
              onClick={() => {
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
            >
              Collapse dense clusters
            </button>
          </div>
        </div>
        <GraphLegend items={LEGEND_ITEMS} className="xl:w-48" />
      </div>

      <div
        className="relative min-h-[16rem] flex-1 overflow-hidden rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-base)]"
        data-reduced-motion={reducedMotion ? 'true' : 'false'}
      >
        <SigmaCanvas
          className="absolute inset-0"
          onAdapterReady={handleAdapterReady}
          onNodeClick={handleNodeClick}
          onStageClick={() => {
            setSelectedEntityId(null);
          }}
          onNodeHover={setHoveredNodeId}
        />
      </div>

      <aside
        aria-label="Accessible graph entity list"
        data-testid="graph-entity-list"
        className="max-h-40 overflow-auto rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] p-2"
      >
        <p className="mb-2 text-xs font-semibold text-[var(--aegis-text-muted)]">
          Nodes ({filteredNodeIds.length}) — keyboard accessible list
        </p>
        <ul className="flex flex-col gap-1">
          {filteredNodeIds.map((nodeId) => (
            <li key={nodeId}>
              <button
                type="button"
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-[var(--aegis-surface-elevated)] aria-pressed:bg-[var(--aegis-surface-elevated)]"
                aria-pressed={selectedEntityId === nodeId}
                data-testid={`graph-entity-${nodeId}`}
                onClick={() => {
                  handleNodeClick(nodeId);
                }}
              >
                {nodeLabels.get(nodeId) ?? nodeId}
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
