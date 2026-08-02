'use client';

import { useMemo } from 'react';

import type { GraphSnapshotV1 } from '@aegis/contracts-ts';

import { useLiveRun } from '@/features/live-run';
import { useRunGraph } from '@/features/shell/hooks/use-shell-queries';

export interface InspectorGraph {
  snapshot: GraphSnapshotV1 | null;
  isPending: boolean;
  isError: boolean;
  refetch: () => void;
}

/**
 * The graph projection the inspector should read.
 *
 * `useRunGraph` fetches the persisted snapshot exactly once and nothing invalidates it, so
 * during a live run it freezes at whatever the estate looked like when the panel mounted.
 * The inspector was reading it anyway — which is why an executed containment showed the
 * asset as `normal` with no applied-control badge no matter how long the operator waited:
 * the control had landed in the live graph store, and the inspector was looking somewhere
 * else. The pending "applying" chip then aged out on its TTL, so the acknowledgment
 * vanished and nothing durable ever replaced it.
 *
 * In live mode the mutable store is authoritative — every `sim.asset.status_changed` delta
 * is folded into it by the event projector — and re-exporting it on each `graphRevision`
 * bump is the same contract the status strip's posture read already follows. Fixture and
 * replay-adjacent views keep the REST snapshot, which is the only projection they have.
 */
export function useInspectorGraph(runId: string): InspectorGraph {
  const liveRun = useLiveRun();
  // A live run only has a graph once its bootstrap has landed; until then the fetch is the
  // only projection there is.
  const graphStore =
    liveRun !== null && liveRun.isLiveMode && liveRun.bootstrapSnapshot !== null
      ? liveRun.graphStore
      : null;
  const live = graphStore !== null;
  const graphQuery = useRunGraph(runId, { enabled: Boolean(runId) && !live });

  // The store's mutation counter. The store object is stable across deltas, so it is the
  // revision — not the reference — that says a previous export has gone stale.
  const graphRevision = liveRun === null ? 0 : liveRun.graphRevision;
  const restSnapshot = graphQuery.data?.snapshot ?? null;

  const snapshot = useMemo(
    () => (graphStore === null ? restSnapshot : graphStore.exportSnapshot()),
    [graphStore, graphRevision, restSnapshot],
  );

  return {
    snapshot,
    // A live run needs no fetch to have a graph, so it is never pending or in error here.
    isPending: live ? false : graphQuery.isPending,
    isError: live ? false : graphQuery.isError,
    refetch: () => {
      if (!live) {
        void graphQuery.refetch();
      }
    },
  };
}
