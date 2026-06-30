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
  type GraphVisualState,
} from '@/features/operational-graph/contracts/graph-visual-state';
import { filterNodesBySearch } from '@/features/operational-graph/layout/initial-layout';
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
  const positionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const [adapterReady, setAdapterReady] = useState(false);
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

  const setSearchQuery = useGraphVisualStore((s) => s.setSearchQuery);
  const setFilterSet = useGraphVisualStore((s) => s.setFilterSet);
  const setHoveredNodeId = useGraphVisualStore((s) => s.setHoveredNodeId);
  const setHighlight = useGraphVisualStore((s) => s.setHighlight);
  const clearHighlight = useGraphVisualStore((s) => s.clearHighlight);
  const setPathModeActive = useGraphVisualStore((s) => s.setPathModeActive);
  const toggleOverlay = useGraphVisualStore((s) => s.toggleOverlay);

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
    const state = buildVisualStateWithPositions(
      useGraphVisualStore.getState().visualState,
      positionsRef,
    );
    const projection = adapter.syncFromStore(store, state.filterSet as GraphFilterSet, state);
    for (const id of projection.visibleNodeIds) {
      const attrs = adapter.getPresentationGraph().getNodeAttributes(id);
      positionsRef.current[id] = { x: attrs.x as number, y: attrs.y as number };
    }
  }, [store]);

  useEffect(() => {
    if (adapterReady) {
      runSync();
    }
  }, [
    adapterReady,
    runSync,
    filterSet,
    selection,
    hoveredNodeId,
    highlightMode,
    highlightedNodeIds,
    highlightedEdgeIds,
    isolationActive,
    overlayToggles,
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

  const handleAdapterReady = useCallback((adapter: SigmaOperationalGraphAdapter) => {
    adapterRef.current = adapter;
    setAdapterReady(true);
  }, []);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
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
    [setSelectedEntityId, pathModeActive],
  );

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

  const filteredNodeIds = useMemo(() => {
    const exported = store.exportSnapshot();
    const allIds = exported.nodes.map((n) => n.id);
    return filterNodesBySearch(allIds, nodeLabels, searchQuery);
  }, [store, nodeLabels, searchQuery]);

  return (
    <div className="flex min-h-[20rem] flex-col gap-3" data-testid="operational-graph-view">
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
