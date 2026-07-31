'use client';

import { useEffect } from 'react';

import { useQuery, useQueryClient } from '@tanstack/react-query';

import { useLiveRun } from '@/features/live-run';
import { apiFetch } from '@/lib/api/auth-fetch';
import { ApiClientError } from '@/lib/api/types';

import type { RunFeedEntry, RunFeedPage } from './contracts';
import { pollIntervalWhileHealthy } from '@/lib/api/retry-policy';

/** Safety cap on cursor-follow paging so a long run cannot spin unbounded. */
const MAX_FEED_PAGES = 12;
const FEED_PAGE_LIMIT = 200;

function feedKey(runId: string) {
  return ['runs', runId, 'ops-feed'] as const;
}

async function fetchFeedPage(
  runId: string,
  cursor: number | null,
  signal: AbortSignal | undefined,
): Promise<RunFeedPage> {
  const query =
    cursor !== null
      ? `?cursor=${String(cursor)}&limit=${String(FEED_PAGE_LIMIT)}`
      : `?limit=${String(FEED_PAGE_LIMIT)}`;
  const response = await apiFetch(`/api/v1/runs/${runId}/feed${query}`, { signal });
  if (!response.ok) {
    throw new ApiClientError({
      code: 'HTTP_ERROR',
      message: `Failed to load run feed (status ${String(response.status)})`,
      status: response.status,
    });
  }
  return (await response.json()) as RunFeedPage;
}

/**
 * Walk the cursor-paged feed to its tail and return every entry (ascending by sequence).
 *
 * The feed is a thin projection over categorised domain events (agent findings, proposals,
 * approvals, alerts, incidents, operator actions, reveals, RoE changes) — not raw telemetry
 * — so its cardinality is modest and paging to the end is cheap. The safety cap keeps a
 * pathologically long run from spinning; the newest page always wins on the caller's side.
 */
async function fetchAllFeedEntries(
  runId: string,
  signal: AbortSignal | undefined,
): Promise<RunFeedEntry[]> {
  const entries: RunFeedEntry[] = [];
  let cursor: number | null = null;
  for (let page = 0; page < MAX_FEED_PAGES; page += 1) {
    const result: RunFeedPage = await fetchFeedPage(runId, cursor, signal);
    entries.push(...result.entries);
    const next = result.nextCursor ?? null;
    if (next === null) {
      break;
    }
    cursor = next;
  }
  return entries;
}

export interface UseRunFeedOptions {
  enabled?: boolean;
}

/**
 * Live ops-feed data source: the merged, categorised heartbeat of the run.
 *
 * Data comes from `GET /runs/{id}/feed` (durable, ownership-gated). It is kept live two
 * ways: a modest poll, and an invalidation whenever the live-run graph revision advances
 * (a new sequenced event landed), so findings/alerts/reveals surface promptly without
 * threading a second WS subscription through the provider. Ascending entries are returned;
 * presentation decides ordering and collapsing.
 */
export function useRunFeed(runId: string, options?: UseRunFeedOptions) {
  const queryClient = useQueryClient();
  const liveRun = useLiveRun();
  const graphRevision = liveRun?.graphRevision ?? 0;

  const query = useQuery<RunFeedEntry[]>({
    queryKey: feedKey(runId),
    queryFn: ({ signal }) => fetchAllFeedEntries(runId, signal),
    enabled: (options?.enabled ?? true) && Boolean(runId),
    // Ambient heartbeat: a missed poll should degrade quietly, not error the panel, and
    // a dead endpoint should be polled progressively less often rather than every 6s.
    refetchInterval: pollIntervalWhileHealthy(6_000),
    retry: false,
    staleTime: 2_000,
  });

  // Nudge a refetch as soon as a new sequenced event advances the live graph, so the feed
  // reflects freshly-landed activity between polls. Cheap: the query dedupes in-flight work.
  useEffect(() => {
    if (graphRevision > 0) {
      void queryClient.invalidateQueries({ queryKey: feedKey(runId) });
    }
  }, [graphRevision, queryClient, runId]);

  return query;
}
