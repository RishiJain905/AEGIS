'use client';

import { ErrorState, LoadingState } from '@aegis/ui';

import { AlertsPanel } from '@/features/alerts';
import { ACTIVITY_COPY, useLiveRun, useRunActivity } from '@/features/live-run';
import {
  useRunAlerts,
  useRunGraph,
  useRunIncidents,
} from '@/features/shell/hooks/use-shell-queries';

/**
 * The quiet-floor state for the Alerts tab. `AlertsPanel` renders nothing until the first
 * card exists, so before then this speaks for the tab — and it answers the question an
 * empty alert rail actually raises: is nothing happening, or is the fog just holding?
 * The wording comes from the run's live activity reading, not a static platitude.
 */
function QuietFloor() {
  const activity = useRunActivity();
  const copy = ACTIVITY_COPY[activity.level];

  return (
    <div
      className="flex flex-col items-center gap-2 rounded-[var(--aegis-radius-md)] border border-dashed border-[var(--aegis-border-subtle)] px-4 py-8 text-center"
      data-testid="alerts-quiet-floor"
      data-level={activity.level}
    >
      <p className="font-[family-name:var(--aegis-font-display)] text-[0.8125rem] font-semibold uppercase tracking-[0.06em] text-[var(--aegis-text-primary)]">
        No alerts yet
      </p>
      <p className="max-w-[16rem] text-xs leading-5 text-[var(--aegis-text-secondary)]">
        {copy.detail} Detections land here the moment a detector fires.
      </p>
    </div>
  );
}

export interface AlertsTabProps {
  runId: string;
}

/**
 * The alerts surface's content: what needs the operator's attention. Wraps the alerts
 * rail (activity strip, dedupe, lifecycle, outcomes) with run-scoped data and a live
 * quiet state. The signals stack re-containers this over the stage; the <xl stacked
 * fallback renders it as a full-width section.
 */
export function AlertsTab({ runId }: AlertsTabProps) {
  const liveRun = useLiveRun();
  const alertsQuery = useRunAlerts(runId);
  const incidentsQuery = useRunIncidents(runId);
  const graphQuery = useRunGraph(runId);

  if (alertsQuery.isPending || incidentsQuery.isPending || graphQuery.isPending) {
    return <LoadingState message="Loading alerts…" />;
  }
  if (alertsQuery.isError) {
    return (
      <ErrorState
        message="Unable to load alerts."
        onRetry={() => {
          void alertsQuery.refetch();
        }}
      />
    );
  }

  const alerts = alertsQuery.data;
  const timelineEntries = liveRun?.state.timelineEntries;
  // Reveals render inside AlertsPanel even with zero alerts; only claim a quiet floor
  // when neither alerts nor hidden-condition reveals exist.
  const hasReveals = (timelineEntries ?? []).some((entry) =>
    entry.eventType.startsWith('sim.hidden_condition.'),
  );

  return (
    <div className="flex min-w-0 flex-col gap-4" data-testid="alerts-tab">
      <AlertsPanel
        alerts={alerts}
        incidents={incidentsQuery.data ?? []}
        snapshot={graphQuery.data?.snapshot ?? null}
        timelineEntries={timelineEntries}
      />
      {alerts.length === 0 && !hasReveals ? <QuietFloor /> : null}
    </div>
  );
}
