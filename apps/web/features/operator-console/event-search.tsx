'use client';

import { useState } from 'react';

import { Alert, Button, EmptyState, LoadingState, cn } from '@aegis/ui';

import {
  useConsoleSearch,
  type ConsoleEvent,
  type ConsoleSearchFilters,
} from '@/features/command-surface';

function nullIfBlank(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function payloadPreview(payload: Record<string, unknown>): string {
  try {
    const json = JSON.stringify(payload);
    if (!json || json === '{}') {
      return '';
    }
    return json.length > 160 ? `${json.slice(0, 160)}…` : json;
  } catch {
    return '';
  }
}

const inputClass =
  'w-full rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-2.5 py-1.5 text-xs text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none';
const labelClass = 'font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]';

function EventRow({ event }: { event: ConsoleEvent }) {
  const preview = payloadPreview(event.payload);
  return (
    <li className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-[11px] text-[var(--aegis-accent-strong)]">
          {event.type}
        </code>
        <code
          className="font-mono text-[10px] text-[var(--aegis-text-muted)]"
          data-testid="console-event-id"
        >
          {event.eventId}
        </code>
        <span className="ml-auto font-mono text-[10px] tabular-nums text-[var(--aegis-text-muted)]">
          {event.simTime}
        </span>
      </div>
      {event.assetId ? (
        <p className="mt-1 font-mono text-[10px] text-[var(--aegis-text-secondary)]">
          {event.assetId}
        </p>
      ) : null}
      {preview ? (
        <p className="mt-1 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
          {preview}
        </p>
      ) : null}
    </li>
  );
}

export function EventSearch({ runId }: { runId: string }) {
  const consoleSearch = useConsoleSearch(runId);
  const [text, setText] = useState('');
  const [assetId, setAssetId] = useState('');
  const [typePrefix, setTypePrefix] = useState('');
  const [fromTime, setFromTime] = useState('');
  const [toTime, setToTime] = useState('');

  const submit = () => {
    const filters: ConsoleSearchFilters = {
      text: nullIfBlank(text),
      assetId: nullIfBlank(assetId),
      eventTypePrefix: nullIfBlank(typePrefix),
      fromSimTime: nullIfBlank(fromTime),
      toSimTime: nullIfBlank(toTime),
    };
    consoleSearch.search(filters);
  };

  const clear = () => {
    setText('');
    setAssetId('');
    setTypePrefix('');
    setFromTime('');
    setToTime('');
    consoleSearch.reset();
  };

  return (
    <div className="flex flex-col gap-3" data-testid="console-event-search">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="flex flex-col gap-2"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="console-text" className={labelClass}>
            Search text
          </label>
          <input
            id="console-text"
            className={inputClass}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
            }}
            placeholder="Match event type or payload…"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label htmlFor="console-asset" className={labelClass}>
              Asset
            </label>
            <input
              id="console-asset"
              className={inputClass}
              value={assetId}
              onChange={(e) => {
                setAssetId(e.target.value);
              }}
              placeholder="asset:…"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="console-type" className={labelClass}>
              Type prefix
            </label>
            <input
              id="console-type"
              className={inputClass}
              value={typePrefix}
              onChange={(e) => {
                setTypePrefix(e.target.value);
              }}
              placeholder="telemetry."
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="console-from" className={labelClass}>
              From (sim time)
            </label>
            <input
              id="console-from"
              className={inputClass}
              value={fromTime}
              onChange={(e) => {
                setFromTime(e.target.value);
              }}
              placeholder="2026-01-01T00:00:00Z"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="console-to" className={labelClass}>
              To (sim time)
            </label>
            <input
              id="console-to"
              className={inputClass}
              value={toTime}
              onChange={(e) => {
                setToTime(e.target.value);
              }}
              placeholder="2026-01-01T01:00:00Z"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit" size="sm" disabled={consoleSearch.isPending}>
            {consoleSearch.isPending ? 'Searching…' : 'Search evidence'}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={clear}>
            Clear
          </Button>
        </div>
      </form>

      <div className="flex flex-col gap-2" aria-live="polite">
        {consoleSearch.isError ? (
          <Alert variant="error">
            {consoleSearch.error instanceof Error
              ? consoleSearch.error.message
              : 'The search failed.'}
          </Alert>
        ) : null}
        {consoleSearch.isPending && consoleSearch.events.length === 0 ? (
          <LoadingState message="Querying the evidence pool…" />
        ) : consoleSearch.hasSearched &&
          consoleSearch.events.length === 0 &&
          !consoleSearch.isPending ? (
          <EmptyState
            title="No matching events"
            description="Widen the filters and search again."
          />
        ) : consoleSearch.events.length > 0 ? (
          <>
            <ul className="flex flex-col gap-1.5">
              {consoleSearch.events.map((event) => (
                <EventRow key={event.eventId} event={event} />
              ))}
            </ul>
            {consoleSearch.hasMore ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  consoleSearch.loadMore();
                }}
                disabled={consoleSearch.isPending}
                className={cn('self-center')}
              >
                {consoleSearch.isPending ? 'Loading…' : 'Load more'}
              </Button>
            ) : null}
          </>
        ) : (
          <p className="px-1 py-4 text-center text-xs text-[var(--aegis-text-muted)]">
            Search the run’s events the way the agents do — by asset, type, text, or time window.
          </p>
        )}
      </div>
    </div>
  );
}
