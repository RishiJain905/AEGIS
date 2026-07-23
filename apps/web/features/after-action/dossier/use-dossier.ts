'use client';

import { useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';

import type { GraphSnapshotV1, RunScoreV1, RunV1 } from '@aegis/contracts-ts';

import { useRun, useRunGraph } from '@/features/shell/hooks/use-shell-queries';
import { useAfterActionView } from '@/features/after-action/use-after-action-queries';

import { assembleAdversaryDossier, type AdversaryDossierViewModel } from './assemble-dossier';
import { fetchAllRunEvents } from './fetch-run-events';

// A run is post-run (dossier may be sealed/opened) once it leaves the active lifecycle.
// Mirrors services/simulation ACTIVE_RUN_STATUSES so the client fog gate matches the server.
const ACTIVE_STATUSES = new Set(['created', 'running', 'paused']);

export function isTerminalRunStatus(status: string | undefined): boolean {
  return status !== undefined && status.length > 0 && !ACTIVE_STATUSES.has(status);
}

export interface DossierQueryResult {
  /** True once the run is terminal and the dossier may reveal ground truth. */
  sealed: boolean;
  runStatus: string | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  dossier: AdversaryDossierViewModel | null;
}

function buildAssetLabelMap(snapshot: GraphSnapshotV1 | null | undefined): Record<string, string> {
  const map: Record<string, string> = {};
  if (!snapshot) {
    return map;
  }
  for (const node of snapshot.nodes) {
    map[node.id] = node.label;
  }
  return map;
}

/**
 * Assemble the adversary dossier for a run. While the run is live the event stream is NOT
 * fetched (its terminal gate keeps ground truth from ever reaching the client), and the
 * hook reports `sealed: false` so the view renders its locked state instead.
 */
export function useAdversaryDossier(runId: string): DossierQueryResult {
  const runQuery = useRun(runId);
  const run: RunV1 | undefined = runQuery.data;
  const sealed = isTerminalRunStatus(run?.status);

  const afterActionQuery = useAfterActionView(runId);
  const score: RunScoreV1 | null | undefined = afterActionQuery.data?.score;

  const eventsQuery = useQuery({
    queryKey: ['dossier', 'events', runId],
    queryFn: ({ signal }) => fetchAllRunEvents(runId, signal),
    enabled: Boolean(runId) && sealed,
    staleTime: 5 * 60_000,
  });

  const graphQuery = useRunGraph(runId, { enabled: Boolean(runId) && sealed });
  const assetLabels = useMemo(
    () => buildAssetLabelMap(graphQuery.data?.snapshot),
    [graphQuery.data?.snapshot],
  );

  const dossier = useMemo<AdversaryDossierViewModel | null>(() => {
    if (!sealed || !eventsQuery.data) {
      return null;
    }
    return assembleAdversaryDossier({
      runId,
      events: eventsQuery.data,
      score: score ?? null,
      runStartSimTime: run?.startedAt,
      runEndSimTime: run?.simTime,
      assetLabels,
    });
  }, [sealed, eventsQuery.data, runId, score, run?.startedAt, run?.simTime, assetLabels]);

  return {
    sealed,
    runStatus: run?.status,
    isLoading: runQuery.isLoading || (sealed && eventsQuery.isLoading),
    isError: runQuery.isError || eventsQuery.isError,
    error: runQuery.error ?? eventsQuery.error,
    dossier,
  };
}
