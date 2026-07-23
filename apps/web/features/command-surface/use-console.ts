'use client';

import { useState } from 'react';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/auth-fetch';
import { ApiClientError } from '@/lib/api/types';

import type {
  ConsoleEvent,
  ConsoleEventSearchRequest,
  ConsoleEventSearchResult,
  OperatorHypothesis,
} from './contracts';

export interface ConsoleSearchFilters {
  assetId?: string | null;
  eventTypePrefix?: string | null;
  text?: string | null;
  fromSimTime?: string | null;
  toSimTime?: string | null;
}

async function postSearch(
  runId: string,
  request: ConsoleEventSearchRequest,
): Promise<ConsoleEventSearchResult> {
  const response = await apiFetch(`/api/v1/runs/${runId}/console/events/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    let envelope: { code?: string; message?: string } | undefined;
    try {
      envelope = (await response.json()) as typeof envelope;
    } catch {
      envelope = undefined;
    }
    throw new ApiClientError({
      code: envelope?.code ?? 'HTTP_ERROR',
      message: envelope?.message ?? `Console search failed (status ${String(response.status)})`,
      status: response.status,
    });
  }
  return (await response.json()) as ConsoleEventSearchResult;
}

/**
 * Operator log/event search — the player's read peer to the agents' `search_events` tool.
 *
 * Accumulates cursor-paged results client-side so "Load more" appends rather than replaces.
 * A fresh `search(filters)` resets the accumulator and cursor; `loadMore()` continues from
 * the last `nextCursor`. Filters map 1:1 onto `ConsoleEventSearchRequestV1`.
 */
export function useConsoleSearch(runId: string) {
  const [events, setEvents] = useState<ConsoleEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [activeFilters, setActiveFilters] = useState<ConsoleSearchFilters | null>(null);

  const mutation = useMutation<
    ConsoleEventSearchResult,
    ApiClientError,
    { filters: ConsoleSearchFilters; cursor: number | null; append: boolean }
  >({
    mutationFn: ({ filters, cursor }) =>
      postSearch(runId, {
        schemaVersion: 1,
        assetId: filters.assetId ?? null,
        eventTypePrefix: filters.eventTypePrefix ?? null,
        text: filters.text ?? null,
        fromSimTime: filters.fromSimTime ?? null,
        toSimTime: filters.toSimTime ?? null,
        cursor,
        limit: 100,
      }),
    onSuccess: (result, variables) => {
      setEvents((prev) => (variables.append ? [...prev, ...result.events] : result.events));
      setNextCursor(result.nextCursor);
    },
  });

  const search = (filters: ConsoleSearchFilters) => {
    setActiveFilters(filters);
    mutation.mutate({ filters, cursor: null, append: false });
  };

  const loadMore = () => {
    if (nextCursor === null || activeFilters === null) {
      return;
    }
    mutation.mutate({ filters: activeFilters, cursor: nextCursor, append: true });
  };

  const reset = () => {
    setEvents([]);
    setNextCursor(null);
    setActiveFilters(null);
    mutation.reset();
  };

  return {
    events,
    nextCursor,
    hasMore: nextCursor !== null,
    hasSearched: activeFilters !== null,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    search,
    loadMore,
    reset,
  };
}

// --- Operator hypotheses (local ledger; degrades until the backend endpoint lands) --------

function newHypothesisId(): string {
  return `hyp-local-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Operator-pinned hypothesis ledger.
 *
 * The backend `POST/GET /console/hypotheses` endpoints are not live yet, so this keeps a
 * per-run in-memory ledger the operator can pin and revise. When the endpoints land, swap
 * the create/list bodies for API calls behind the same interface — call sites are unchanged.
 * (In-memory by design: hypotheses are a live-session scratchpad, not durable state, until
 * the server owns them.)
 */
export function useOperatorHypotheses(_runId: string) {
  const [hypotheses, setHypotheses] = useState<OperatorHypothesis[]>([]);

  const add = (input: { statement: string; assetIds?: string[]; confidence?: number }) => {
    const statement = input.statement.trim();
    if (!statement) {
      return;
    }
    setHypotheses((prev) => [
      {
        id: newHypothesisId(),
        statement,
        assetIds: input.assetIds ?? [],
        confidence: input.confidence ?? 0.5,
        createdAt: new Date().toISOString(),
        local: true,
      },
      ...prev,
    ]);
  };

  const remove = (id: string) => {
    setHypotheses((prev) => prev.filter((entry) => entry.id !== id));
  };

  return { hypotheses, add, remove };
}
