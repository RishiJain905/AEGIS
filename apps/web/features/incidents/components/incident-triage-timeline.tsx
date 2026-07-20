'use client';

import { EmptyState, Panel, cn } from '@aegis/ui';

import type { TriageEvent, TriageEventTone } from '../lib/incident-model';

const TONE_DOT: Record<TriageEventTone, string> = {
  info: 'bg-[var(--aegis-status-under-investigation)]',
  watch: 'bg-[var(--aegis-status-suspicious)]',
  danger: 'bg-[var(--aegis-status-compromised)]',
  success: 'bg-[var(--aegis-status-contained)]',
};

function formatTimestamp(iso: string): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) {
    return iso;
  }
  return new Date(parsed).toISOString().replace('T', ' ').slice(0, 19) + 'Z';
}

export function IncidentTriageTimeline({ events }: { events: readonly TriageEvent[] }) {
  return (
    <Panel
      title="Triage timeline"
      description="Alert raised through investigation, proposals, approval, and resolution."
      data-testid="incident-triage-timeline"
    >
      {events.length === 0 ? (
        <EmptyState
          title="No triage activity"
          description="This incident has no recorded triage events yet."
        />
      ) : (
        <ol className="flex flex-col gap-0" role="list">
          {events.map((event, index) => (
            <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    'mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-[var(--aegis-surface-panel)]',
                    TONE_DOT[event.tone],
                  )}
                  aria-hidden="true"
                />
                {index < events.length - 1 ? (
                  <span
                    className="mt-1.5 w-px flex-1 bg-[var(--aegis-border-subtle)]"
                    aria-hidden="true"
                  />
                ) : null}
              </div>
              <div className="min-w-0 flex-1 pb-1">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-sm font-medium text-[var(--aegis-text-primary)]">
                    {event.title}
                  </span>
                  {event.role ? (
                    <span className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-accent-strong)]">
                      {event.role}
                    </span>
                  ) : null}
                </div>
                {event.detail ? (
                  <p className="mt-0.5 text-xs leading-5 text-[var(--aegis-text-secondary)]">
                    {event.detail}
                  </p>
                ) : null}
                <time
                  className="mt-0.5 block font-mono text-[0.625rem] text-[var(--aegis-text-muted)] tabular-nums"
                  dateTime={event.timestamp}
                >
                  {formatTimestamp(event.timestamp)}
                </time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
