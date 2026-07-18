'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import {
  createGraphStore,
  GraphLayer,
  type GraphFilterSet,
  type GraphStore,
} from '@aegis/graph-domain';
import {
  Alert,
  Button,
  ErrorState,
  GraphIsolationControls,
  GraphLayerControls,
  GraphOverlayToggle,
  LoadingState,
  useReducedMotion,
} from '@aegis/ui';

import { createSemanticSceneAdapter } from '@/features/cinematic-graph/adapters/semantic-scene-adapter';
import { CapabilityFallbackNotice } from '@/features/cinematic-graph/components/capability-fallback';
import {
  GraphViewMode,
  RenderQualityTier,
  SemanticSceneAdapterError,
  type SceneProjection,
  type SemanticSceneAdapter,
} from '@/features/cinematic-graph/contracts';
import { probeCapabilityReport } from '@/features/cinematic-graph/lib/capability';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { GraphHighlightMode } from '@/features/operational-graph/contracts/graph-visual-state';
import { computeHighlight } from '@/features/operational-graph/semantic/graph-highlights';
import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const LAYER_OPTIONS = [
  { id: GraphLayer.INFRASTRUCTURE, label: 'Infrastructure' },
  { id: GraphLayer.ACTIVITY, label: 'Activity' },
  { id: GraphLayer.SECURITY_STATE, label: 'Security' },
  { id: GraphLayer.INVESTIGATION, label: 'Investigation' },
  { id: GraphLayer.PRESENTATION, label: 'Presentation' },
];

const CinematicSceneCanvas = dynamic(
  () =>
    import('@/features/cinematic-graph/components/cinematic-scene-canvas').then((mod) => ({
      default: mod.CinematicSceneCanvas,
    })),
  {
    ssr: false,
    loading: () => <LoadingState message="Initializing Three.js semantic renderer…" />,
  },
);

const EMPTY_NODE_IDS: string[] = [];

export interface CinematicGraphViewProps {
  snapshot: GraphSnapshotV1;
  runId: string;
  graphStore?: GraphStore;
  graphRevision?: number;
  evidenceNodeIds?: string[];
  /** Node ids in incident scope; defaults to status-derived membership. */
  incidentNodeIds?: string[];
}

function useGraphStoreInstance(snapshot: GraphSnapshotV1, externalStore?: GraphStore): GraphStore {
  const internalStore = useMemo(() => {
    const store = createGraphStore();
    store.loadSnapshot(snapshot);
    return store;
  }, [snapshot.runId, snapshot.sequence, snapshot.revision]);
  return externalStore ?? internalStore;
}

function sceneBoundsKey(projection: SceneProjection): string | null {
  if (projection.nodes.length === 0) {
    return null;
  }

  const xs = projection.nodes.map((node) => node.position.x);
  const ys = projection.nodes.map((node) => node.position.y);
  const zs = projection.nodes.map((node) => node.position.z);
  return [
    projection.runId,
    projection.sequence,
    projection.revision,
    projection.nodes.length,
    Math.min(...xs),
    Math.max(...xs),
    Math.min(...ys),
    Math.max(...ys),
    Math.min(...zs),
    Math.max(...zs),
  ].join(':');
}

export function CinematicGraphView({
  snapshot,
  graphStore,
  graphRevision = 0,
  evidenceNodeIds = EMPTY_NODE_IDS,
  incidentNodeIds,
}: CinematicGraphViewProps) {
  const store = useGraphStoreInstance(snapshot, graphStore);
  // Same status-derived incident approximation the 2D view and replay use, so
  // the Incident overlay stays consistent across renderers.
  const effectiveIncidentNodeIds = useMemo(() => {
    if (incidentNodeIds) {
      return incidentNodeIds;
    }
    return snapshot.nodes
      .filter(
        (node) =>
          node.status === 'under_investigation' ||
          node.status === 'compromised' ||
          node.status === 'contained',
      )
      .map((node) => node.id);
  }, [incidentNodeIds, snapshot.nodes]);
  const adapterRef = useRef<SemanticSceneAdapter | null>(null);
  const framedSceneKeyRef = useRef<string | null>(null);
  const [projection, setProjection] = useState<SceneProjection | null>(null);
  const [canvasGeneration, setCanvasGeneration] = useState(0);
  const [syncError, setSyncError] = useState<{
    code: string;
    message: string;
  } | null>(null);
  const reducedMotion = useReducedMotion();

  const filterSet = useGraphVisualStore((s) => s.visualState.filterSet);
  const selection = useGraphVisualStore((s) => s.visualState.selection);
  const highlightMode = useGraphVisualStore((s) => s.visualState.highlightMode);
  const highlightedNodeIds = useGraphVisualStore((s) => s.visualState.highlightedNodeIds);
  const highlightedEdgeIds = useGraphVisualStore((s) => s.visualState.highlightedEdgeIds);
  const isolationActive = useGraphVisualStore((s) => s.visualState.isolationActive);
  const overlayToggles = useGraphVisualStore((s) => s.visualState.overlayToggles);
  const nodePositions = useGraphVisualStore((s) => s.visualState.nodePositions);
  const pathModeActive = useGraphVisualStore((s) => s.visualState.pathModeActive);

  const setFilterSet = useGraphVisualStore((s) => s.setFilterSet);
  const toggleOverlay = useGraphVisualStore((s) => s.toggleOverlay);
  const setHighlight = useGraphVisualStore((s) => s.setHighlight);
  const clearHighlight = useGraphVisualStore((s) => s.clearHighlight);
  const setPathModeActive = useGraphVisualStore((s) => s.setPathModeActive);

  const setSelectedEntityId = useWorkspaceUiStore((s) => s.setSelectedEntityId);
  const selectedEntityId = useWorkspaceUiStore((s) => s.workspace.selectedEntityId);
  const setSelection = useGraphVisualStore((s) => s.setSelection);

  const capability = useCinematicGraphStore((s) => s.capability);
  const qualityTier = useCinematicGraphStore((s) => s.qualityTier);
  const camera = useCinematicGraphStore((s) => s.camera);
  const setCapability = useCinematicGraphStore((s) => s.setCapability);
  const setCamera = useCinematicGraphStore((s) => s.setCamera);
  const setViewMode = useCinematicGraphStore((s) => s.setViewMode);
  const setLastError = useCinematicGraphStore((s) => s.setLastError);

  useEffect(() => {
    const report = probeCapabilityReport({ reducedMotion });
    setCapability(report);
  }, [reducedMotion, setCapability]);

  useEffect(() => {
    const adapter = createSemanticSceneAdapter();
    adapterRef.current = adapter;
    return () => {
      adapter.dispose();
      adapterRef.current = null;
    };
  }, []);

  const runSync = useCallback(() => {
    const adapter = adapterRef.current;
    if (!adapter) {
      return;
    }
    try {
      adapter.setCapabilityReport(capability);
      const visualState = {
        ...useGraphVisualStore.getState().visualState,
        selection: {
          ...useGraphVisualStore.getState().visualState.selection,
          primaryNodeId:
            useGraphVisualStore.getState().visualState.selection.primaryNodeId ?? selectedEntityId,
        },
      };
      const next = adapter.syncFromStore(store, filterSet as GraphFilterSet, visualState, {
        nodePositions,
        qualityTier,
        evidenceNodeIds: new Set(evidenceNodeIds),
        incidentNodeIds: new Set(effectiveIncidentNodeIds),
      });
      setProjection(next);
      setCamera(next.camera);
      setSyncError(null);
      setLastError(null);
    } catch (error) {
      const code =
        error instanceof SemanticSceneAdapterError ? error.code : 'cinematic_sync_failed';
      const message = error instanceof Error ? error.message : 'Failed to sync 3D scene';
      setSyncError({ code, message });
      setLastError({ code, message });
      setProjection(null);
    }
  }, [
    capability,
    evidenceNodeIds,
    filterSet,
    effectiveIncidentNodeIds,
    nodePositions,
    qualityTier,
    selectedEntityId,
    setCamera,
    setLastError,
    store,
  ]);

  useEffect(() => {
    runSync();
  }, [
    runSync,
    graphRevision,
    selection.primaryNodeId,
    highlightMode,
    highlightedNodeIds,
    highlightedEdgeIds,
    isolationActive,
    overlayToggles,
    snapshot.sequence,
    snapshot.revision,
  ]);

  useEffect(() => {
    const boundsKey = projection ? sceneBoundsKey(projection) : null;
    if (!boundsKey) {
      framedSceneKeyRef.current = null;
      return;
    }
    if (canvasGeneration === 0) {
      return;
    }

    const sceneKey = `${String(canvasGeneration)}:${boundsKey}`;
    if (framedSceneKeyRef.current === sceneKey) {
      return;
    }

    const bookmark = adapterRef.current?.resetCamera();
    if (!bookmark) {
      return;
    }
    framedSceneKeyRef.current = sceneKey;
    setCamera(bookmark);
  }, [canvasGeneration, projection, setCamera]);

  const handleSelectNode = useCallback(
    (nodeId: string) => {
      setSelectedEntityId(nodeId);
      const current = useGraphVisualStore.getState().visualState;
      if (
        current.pathModeActive &&
        current.selection.primaryNodeId &&
        current.selection.primaryNodeId !== nodeId
      ) {
        setSelection(current.selection.primaryNodeId, nodeId);
      } else {
        setSelection(nodeId, null);
      }
      const bookmark = adapterRef.current?.focusNode(nodeId);
      if (bookmark) {
        setCamera(bookmark);
      }
    },
    [setCamera, setSelectedEntityId, setSelection],
  );

  const handleBackgroundClick = useCallback(() => {
    setSelectedEntityId(null);
    setSelection(null, null);
  }, [setSelectedEntityId, setSelection]);

  const handleLayerToggle = useCallback(
    (layerId: string) => {
      const current = useGraphVisualStore.getState().visualState.filterSet;
      const enabled = current.enabledLayers.includes(layerId)
        ? current.enabledLayers.filter((layer) => layer !== layerId)
        : [...current.enabledLayers, layerId];
      if (enabled.length === 0) {
        return;
      }
      setFilterSet({
        ...current,
        enabledLayers: enabled,
      } as GraphFilterSet);
    },
    [setFilterSet],
  );

  const handleIsolate = useCallback(() => {
    const state = useGraphVisualStore.getState().visualState;
    const primaryId = state.selection.primaryNodeId ?? selectedEntityId;
    if (!primaryId) {
      return;
    }
    const highlight = computeHighlight(store, {
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
  }, [selectedEntityId, setHighlight, store]);

  useEffect(() => {
    if (!pathModeActive || !selection.primaryNodeId || !selection.secondaryNodeId) {
      return;
    }
    const state = useGraphVisualStore.getState().visualState;
    const highlight = computeHighlight(store, {
      ...state,
      highlightMode: GraphHighlightMode.PATH,
    });
    setHighlight(
      GraphHighlightMode.PATH,
      highlight.highlightedNodeIds,
      highlight.highlightedEdgeIds,
      false,
    );
  }, [pathModeActive, selection.primaryNodeId, selection.secondaryNodeId, setHighlight, store]);

  const handleCanvasReady = useCallback(() => {
    setCanvasGeneration((generation) => generation + 1);
  }, []);

  if (qualityTier === RenderQualityTier.FALLBACK_2D || !capability.webglAvailable) {
    return (
      <CapabilityFallbackNotice
        reasonCodes={capability.reasonCodes}
        onReturnTo2d={() => {
          setViewMode(GraphViewMode.TWO_D);
        }}
      />
    );
  }

  if (syncError) {
    return (
      <div data-testid="cinematic-graph-error">
        <ErrorState message={syncError.message} />
        <p className="mt-2 font-mono text-xs" data-testid="cinematic-error-code">
          {syncError.code}
        </p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          data-testid="cinematic-error-return-2d"
          onClick={() => {
            setViewMode(GraphViewMode.TWO_D);
          }}
        >
          Return to 2D operational graph
        </Button>
      </div>
    );
  }

  if (!projection) {
    return <LoadingState message="Projecting semantic graph into 3D scene…" />;
  }

  return (
    <div className="flex min-h-[16rem] flex-col gap-3" data-testid="cinematic-graph-view">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--aegis-text-secondary)]">
        <p data-testid="cinematic-graph-meta">
          Semantic 3D · sequence {String(projection.sequence)} · revision{' '}
          {String(projection.revision)} · {String(projection.nodeCount)} nodes /{' '}
          {String(projection.edgeCount)} edges · tier {qualityTier}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            data-testid="cinematic-reset-camera"
            onClick={() => {
              const bookmark = adapterRef.current?.resetCamera();
              if (bookmark) {
                setCamera(bookmark);
              }
            }}
          >
            Reset camera
          </Button>
          <Button
            variant="outline"
            size="sm"
            data-testid="cinematic-switch-2d"
            onClick={() => {
              setViewMode(GraphViewMode.TWO_D);
            }}
          >
            Switch to 2D
          </Button>
        </div>
      </div>
      {reducedMotion ? (
        <Alert
          variant="info"
          title="Reduced motion"
          className="mb-1"
          data-testid="cinematic-reduced-motion"
        >
          Camera easing is disabled. Semantic node, edge, risk, and status markings remain visible.
        </Alert>
      ) : null}
      <div
        className="grid gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-3 lg:grid-cols-2"
        data-testid="cinematic-control-deck"
      >
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Data layers
          </p>
          <GraphLayerControls
            layers={LAYER_OPTIONS}
            enabledLayers={filterSet.enabledLayers}
            onToggle={handleLayerToggle}
          />
        </div>
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Signal overlays
          </p>
          <GraphOverlayToggle toggles={overlayToggles} onToggle={toggleOverlay} />
        </div>
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Investigation focus
          </p>
          <GraphIsolationControls
            isolationActive={isolationActive}
            onIsolate={handleIsolate}
            onRestore={clearHighlight}
            disabled={!selection.primaryNodeId && !selectedEntityId}
          />
        </div>
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--aegis-text-muted)]">
            Analysis actions
          </p>
          <Button
            variant={pathModeActive ? 'default' : 'outline'}
            size="sm"
            data-testid="cinematic-path-mode"
            aria-pressed={pathModeActive}
            onClick={() => {
              setPathModeActive(!pathModeActive);
            }}
            className="text-xs"
          >
            {pathModeActive ? 'Path mode (select 2 nodes)' : 'Trace path'}
          </Button>
        </div>
      </div>
      <div
        className="h-[clamp(28rem,62vh,46rem)] min-h-[28rem] shrink-0 overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-canvas)] shadow-[var(--aegis-shadow-panel)]"
        data-testid="cinematic-canvas-frame"
      >
        <CinematicSceneCanvas
          nodes={projection.nodes}
          edges={projection.edges}
          camera={camera}
          qualityTier={qualityTier}
          dprCap={capability.devicePixelRatioCap}
          reducedMotion={reducedMotion}
          onReady={handleCanvasReady}
          onSelectNode={handleSelectNode}
          onBackgroundClick={handleBackgroundClick}
        />
      </div>
      <ul
        className="max-h-36 overflow-auto rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] p-2 text-xs"
        data-testid="cinematic-entity-list"
        aria-label="Accessible 3D graph entity list"
      >
        {projection.nodes.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              className="min-h-10 w-full rounded-[var(--aegis-radius-sm)] px-3 py-2 text-left text-[var(--aegis-text-secondary)] transition-colors hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)] aria-pressed:bg-[var(--aegis-accent-soft)] aria-pressed:text-[var(--aegis-accent-strong)]"
              data-testid={`cinematic-entity-${node.id}`}
              aria-pressed={selectedEntityId === node.id}
              onClick={() => {
                handleSelectNode(node.id);
              }}
            >
              {node.label} · risk {node.riskScore.toFixed(2)} · {node.status}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
