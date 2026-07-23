'use client';

import { useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';

import { useRun, useRunGraph } from '@/features/shell/hooks/use-shell-queries';

import { assessIntent, type IntentAssessment } from './assess-intent';
import { buildIntentInput } from './build-intent-input';
import { fetchIntentEvents } from './fetch-intent-events';

// A run may reveal ground truth (and thus be assessed) only once it leaves the active
// lifecycle. Mirrors services/simulation ACTIVE_RUN_STATUSES so the client fog gate matches.
const ACTIVE_STATUSES = new Set(['created', 'running', 'paused']);

function isTerminal(status: string | undefined): boolean {
  return status !== undefined && status.length > 0 && !ACTIVE_STATUSES.has(status);
}

export interface IntentReviewResult {
  /** True once the run is terminal; the intent review only assesses a finished run. */
  sealed: boolean;
  /** The operator's stated intent, or null when none was set at launch. */
  intent: string | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  assessment: IntentAssessment | null;
}

/**
 * Assemble the commander's-intent after-action review for a run. Purely deterministic: the
 * intent text plus the run's ground-truth event stream, run through {@link assessIntent}.
 * While the run is live the event stream is never fetched.
 */
export function useIntentReview(runId: string): IntentReviewResult {
  const runQuery = useRun(runId);
  const run = runQuery.data;
  const intent = run?.commanderIntent ?? null;
  const sealed = isTerminal(run?.status);
  const enabled = Boolean(runId) && sealed && Boolean(intent && intent.trim().length > 0);

  const eventsQuery = useQuery({
    queryKey: ['intent-review', 'events', runId],
    queryFn: ({ signal }) => fetchIntentEvents(runId, signal),
    enabled,
    staleTime: 5 * 60_000,
  });
  const graphQuery = useRunGraph(runId, { enabled });

  const assessment = useMemo<IntentAssessment | null>(() => {
    if (!enabled || !eventsQuery.data) {
      return null;
    }
    const nodes = graphQuery.data?.snapshot?.nodes ?? [];
    return assessIntent(buildIntentInput(intent, nodes, eventsQuery.data));
  }, [enabled, eventsQuery.data, graphQuery.data?.snapshot?.nodes, intent]);

  return {
    sealed,
    intent,
    isLoading: runQuery.isLoading || (enabled && eventsQuery.isLoading),
    isError: runQuery.isError || eventsQuery.isError,
    error: runQuery.error ?? eventsQuery.error,
    assessment,
  };
}
