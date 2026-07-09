'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { createGraphStore, type GraphFilterSet, type GraphStore } from '@aegis/graph-domain';
import { Alert, ErrorState, LoadingState, useReducedMotion } from '@aegis/ui';

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
import { useGraphVisualStore } from '@/features/operational-graph/stores/graph-visual-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

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

export interface CinematicGraphViewProps {
  snapshot: GraphSnapshotV1;
  runId: string;
  graphStore?: GraphStore;
  graphRevision?: number;
  evidenceNodeIds?: string[];
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

export function CinematicGraphView({
  snapshot,
  graphStore,
  graphRevision = 0,
  evidenceNodeIds = [],
  incidentNodeIds = [],
}: CinematicGraphViewProps) {
  const store = useGraphStoreInstance(snapshot, graphStore);
  const adapterRef = useRef<SemanticSceneAdapter | null>(null);
  const [projection, setProjection] = useState<SceneProjection | null>(null);
  const [syncError, setSyncError] = useState<{ code: string; message: string } | null>(null);
  const reducedMotion = useReducedMotion();

  const filterSet = useGraphVisualStore((s) => s.visualState.filterSet);
  const selection = useGraphVisualStore((s) => s.visualState.selection);
  const highlightMode = useGraphVisualStore((s) => s.visualState.highlightMode);
  const highlightedNodeIds = useGraphVisualStore((s) => s.visualState.highlightedNodeIds);
  const highlightedEdgeIds = useGraphVisualStore((s) => s.visualState.highlightedEdgeIds);
  const isolationActive = useGraphVisualStore((s) => s.visualState.isolationActive);
  const overlayToggles = useGraphVisualStore((s) => s.visualState.overlayToggles);
  const nodePositions = useGraphVisualStore((s) => s.visualState.nodePositions);

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
        incidentNodeIds: new Set(incidentNodeIds),
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
    incidentNodeIds,
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

  const handleSelectNode = useCallback(
    (nodeId: string) => {
      setSelectedEntityId(nodeId);
      setSelection(nodeId, null);
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
        <button
          type="button"
          className="mt-3 rounded border border-[var(--aegis-border)] px-2 py-1 text-xs"
          data-testid="cinematic-error-return-2d"
          onClick={() => {
            setViewMode(GraphViewMode.TWO_D);
          }}
        >
          Return to 2D operational graph
        </button>
      </div>
    );
  }

  if (!projection) {
    return <LoadingState message="Projecting semantic graph into 3D scene…" />;
  }

  return (
    <div className="flex h-full min-h-[16rem] flex-col gap-2" data-testid="cinematic-graph-view">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--aegis-text-secondary)]">
        <p data-testid="cinematic-graph-meta">
          Semantic 3D · sequence {String(projection.sequence)} · revision{' '}
          {String(projection.revision)} · {String(projection.nodeCount)} nodes /{' '}
          {String(projection.edgeCount)} edges · tier {qualityTier}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border border-[var(--aegis-border)] px-2 py-1"
            data-testid="cinematic-reset-camera"
            onClick={() => {
              const bookmark = adapterRef.current?.resetCamera();
              if (bookmark) {
                setCamera(bookmark);
              }
            }}
          >
            Reset camera
          </button>
          <button
            type="button"
            className="rounded border border-[var(--aegis-border)] px-2 py-1"
            data-testid="cinematic-switch-2d"
            onClick={() => {
              setViewMode(GraphViewMode.TWO_D);
            }}
          >
            Switch to 2D
          </button>
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
      <div className="min-h-[16rem] flex-1 overflow-hidden rounded border border-[var(--aegis-border)]">
        <CinematicSceneCanvas
          nodes={projection.nodes}
          edges={projection.edges}
          camera={camera}
          qualityTier={qualityTier}
          dprCap={capability.devicePixelRatioCap}
          reducedMotion={reducedMotion}
          onSelectNode={handleSelectNode}
          onBackgroundClick={handleBackgroundClick}
        />
      </div>
      <ul
        className="max-h-28 overflow-auto rounded border border-[var(--aegis-border)] p-2 text-xs"
        data-testid="cinematic-entity-list"
        aria-label="Accessible 3D graph entity list"
      >
        {projection.nodes.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              className="w-full rounded px-2 py-1 text-left hover:bg-[var(--aegis-surface-elevated)]"
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
