'use client';

import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';

import { createGraphStore, type GraphStore } from '@aegis/graph-domain';
import { useReducedMotion } from '@aegis/ui';

import { buildReplayBookmarks } from '@/features/replay/lib/bookmarks';
import {
  createHistoricalGraphStore,
  loadHistoricalGraphStore,
  toHistoricalGraphAdapter,
} from '@/features/replay/lib/historical-graph-adapter';
import { speedToIntervalMs } from '@/features/replay/lib/playback';
import { useApiClient } from '@/lib/api';
import { ApiClientError } from '@/lib/api/types';
import { useReplayStore } from '@/stores/replay-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

interface ReplayContextValue {
  runId: string;
  graphStore: GraphStore;
  graphRevision: number;
  returnToLive: () => void;
}

const ReplayContext = createContext<ReplayContextValue | null>(null);

export function useReplay(): ReplayContextValue | null {
  return useContext(ReplayContext);
}

export interface ReplayProviderProps {
  runId: string;
  children: ReactNode;
  initialSequence?: number;
}

export function ReplayProvider({ runId, children, initialSequence }: ReplayProviderProps) {
  const api = useApiClient();
  const router = useRouter();
  const reducedMotion = useReducedMotion();
  const abortRef = useRef<AbortController | null>(null);
  const graphStoreRef = useRef<GraphStore | null>(null);
  if (!graphStoreRef.current) {
    graphStoreRef.current = createHistoricalGraphStore();
  }

  const enterHistorical = useReplayStore((state) => state.enterHistorical);
  const clear = useReplayStore((state) => state.clear);
  const cursor = useReplayStore((state) => state.cursor);
  const playbackStatus = useReplayStore((state) => state.playbackStatus);
  const speed = useReplayStore((state) => state.speed);
  const beginReconstruction = useReplayStore((state) => state.beginReconstruction);
  const applyReconstructedState = useReplayStore((state) => state.applyReconstructedState);
  const setError = useReplayStore((state) => state.setError);
  const setBookmarks = useReplayStore((state) => state.setBookmarks);
  const setSnapshots = useReplayStore((state) => state.setSnapshots);
  const setReducedMotion = useReplayStore((state) => state.setReducedMotion);
  const setPlaybackStatus = useReplayStore((state) => state.setPlaybackStatus);
  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const returnToLiveStore = useReplayStore((state) => state.returnToLive);
  const reconstructedState = useReplayStore((state) => state.reconstructedState);
  const setPresentationMode = useWorkspaceUiStore((state) => state.setPresentationMode);
  const setTimelineCursorSequence = useWorkspaceUiStore((state) => state.setTimelineCursorSequence);
  const resetForRun = useWorkspaceUiStore((state) => state.resetForRun);

  useEffect(() => {
    resetForRun(runId);
    setPresentationMode('historical');
    let cancelled = false;
    void api
      .getReplayState(runId, { preferSnapshot: true })
      .then((latest) => {
        if (cancelled) {
          return;
        }
        // An unbounded reconstruction lands on the run's last persisted event, so its
        // cursor IS the maximum sequence. Never widen the range past that: scrubbing to
        // an End the run never reached is what made the transport ask for state that
        // does not exist.
        const maxSequence = latest.cursor.sequence;
        enterHistorical(runId, {
          sequence: initialSequence ?? maxSequence,
          maxSequence,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        enterHistorical(runId, {
          sequence: initialSequence ?? 0,
          maxSequence: 0,
        });
        if (error instanceof ApiClientError) {
          useReplayStore.setState({
            loadStatus: error.status === 404 ? 'unavailable' : 'error',
            errorCode: error.code,
            errorMessage: error.message,
          });
        } else {
          setError('REPLAY_VALIDATION_FAILED', 'Unable to open historical replay.');
        }
      });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
      clear();
      setPresentationMode('live');
    };
  }, [
    api,
    clear,
    enterHistorical,
    initialSequence,
    resetForRun,
    runId,
    setError,
    setPresentationMode,
  ]);

  useEffect(() => {
    setReducedMotion(reducedMotion);
  }, [reducedMotion, setReducedMotion]);

  useEffect(() => {
    let cancelled = false;
    void api.listReplaySnapshots(runId).then((snapshots) => {
      if (!cancelled) {
        setSnapshots(snapshots);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [api, runId, setSnapshots]);

  useEffect(() => {
    if (!cursor) {
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const generation = beginReconstruction();
    setTimelineCursorSequence(cursor.sequence);

    void api
      .getReplayState(
        runId,
        {
          sequence: cursor.sequence,
          incidentId: cursor.incidentId,
          preferSnapshot: true,
        },
        controller.signal,
      )
      .then((state) => {
        if (controller.signal.aborted) {
          return;
        }
        const store = graphStoreRef.current ?? createGraphStore();
        graphStoreRef.current = store;
        loadHistoricalGraphStore(store, state.graph);
        applyReconstructedState(generation, state, toHistoricalGraphAdapter(state));
        const snapshots = useReplayStore.getState().snapshots;
        setBookmarks(buildReplayBookmarks(runId, state, snapshots));
        if (state.cursor.sequence > useReplayStore.getState().maxSequence) {
          useReplayStore.setState({ maxSequence: state.cursor.sequence });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        if (error instanceof ApiClientError) {
          const unavailable =
            error.code === 'REPLAY_NOT_FOUND' ||
            error.code === 'SNAPSHOT_MISSING' ||
            error.status === 404;
          useReplayStore.setState({
            loadStatus: unavailable ? 'unavailable' : 'error',
            errorCode: error.code,
            errorMessage: error.message,
            playbackStatus: 'paused',
          });
          return;
        }
        setError('REPLAY_VALIDATION_FAILED', 'Unable to reconstruct historical state.');
      });

    return () => {
      controller.abort();
    };
  }, [
    api,
    applyReconstructedState,
    beginReconstruction,
    cursor?.incidentId,
    cursor?.sequence,
    runId,
    setBookmarks,
    setError,
    setTimelineCursorSequence,
  ]);

  useEffect(() => {
    if (playbackStatus !== 'playing' || reducedMotion) {
      return;
    }
    const intervalMs = speedToIntervalMs(speed, reducedMotion);
    if (!Number.isFinite(intervalMs)) {
      return;
    }
    const timer = window.setInterval(() => {
      const current = useReplayStore.getState();
      if (!current.cursor) {
        return;
      }
      if (current.cursor.sequence >= current.maxSequence) {
        setPlaybackStatus('paused');
        return;
      }
      setCursorSequence(current.cursor.sequence + 1);
    }, intervalMs);
    return () => {
      window.clearInterval(timer);
    };
  }, [playbackStatus, reducedMotion, setCursorSequence, setPlaybackStatus, speed]);

  const graphRevision = reconstructedState?.graph?.revision ?? 0;

  const value = useMemo<ReplayContextValue>(
    () => ({
      runId,
      graphStore: graphStoreRef.current ?? createGraphStore(),
      graphRevision,
      returnToLive: () => {
        const result = returnToLiveStore();
        if (result) {
          router.push(result.liveRoute);
        }
      },
    }),
    [graphRevision, returnToLiveStore, router, runId],
  );

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
}
