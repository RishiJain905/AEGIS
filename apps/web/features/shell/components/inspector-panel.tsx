'use client';

import { Badge, Button, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { GraphEntityInspector, IncidentContextInspector } from '@/features/inspector';
import {
  useIncident,
  useRunAlerts,
  useRunGraph,
  useRunIncidents,
} from '@/features/shell/hooks/use-shell-queries';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

interface InspectorPanelProps {
  runId?: string;
  incidentId?: string;
}

export function InspectorPanel({ runId, incidentId }: InspectorPanelProps) {
  const collapsed = useWorkspaceUiStore(
    (state) => state.panelPreferences.regions.inspector?.collapsed ?? false,
  );
  const togglePanelCollapsed = useWorkspaceUiStore((state) => state.togglePanelCollapsed);
  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const setSelectedEntityId = useWorkspaceUiStore((state) => state.setSelectedEntityId);

  const incidentQuery = useIncident(incidentId ?? '');
  const incidentsQuery = useRunIncidents(runId ?? '');
  const alertsQuery = useRunAlerts(runId ?? '');
  const graphQuery = useRunGraph(runId ?? '');

  if (collapsed) {
    return (
      <div className="flex w-12 shrink-0 flex-col items-center border-l border-[var(--aegis-border-default)] p-2">
        <Button
          variant="ghost"
          size="sm"
          data-testid="expand-inspector"
          onClick={() => {
            togglePanelCollapsed('inspector');
          }}
          aria-label="Expand inspector"
        >
          ‹
        </Button>
      </div>
    );
  }

  const isLoading =
    (incidentId && incidentQuery.isPending) ||
    (runId && (incidentsQuery.isPending || alertsQuery.isPending || graphQuery.isPending));
  const isError =
    (incidentId && incidentQuery.isError) ||
    (runId && (incidentsQuery.isError || alertsQuery.isError || graphQuery.isError));

  const snapshot = graphQuery.data?.snapshot ?? null;

  return (
    <aside
      className="flex w-full shrink-0 flex-col border-l border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] lg:w-80 xl:w-96"
      data-testid="inspector-panel"
      aria-label="Inspector"
    >
      <div className="flex items-center justify-between border-b border-[var(--aegis-border-subtle)] px-4 py-2">
        <h2 className="text-sm font-semibold">Inspector</h2>
        <Button
          variant="ghost"
          size="sm"
          data-testid="collapse-inspector"
          onClick={() => {
            togglePanelCollapsed('inspector');
          }}
          aria-label="Collapse inspector"
        >
          ›
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {isLoading ? <LoadingState message="Loading inspector data…" /> : null}
        {isError ? (
          <ErrorState
            message="Unable to load inspector data."
            onRetry={() => {
              void incidentQuery.refetch();
              void incidentsQuery.refetch();
              void alertsQuery.refetch();
              void graphQuery.refetch();
            }}
          />
        ) : null}

        {!isLoading && !isError ? (
          <div className="flex flex-col gap-4">
            {snapshot ? (
              <GraphEntityInspector snapshot={snapshot} selectedEntityId={selectedEntityId} />
            ) : null}

            {incidentsQuery.data && alertsQuery.data ? (
              <IncidentContextInspector
                incidents={incidentsQuery.data}
                alerts={alertsQuery.data}
                selectedEntityId={selectedEntityId}
              />
            ) : null}

            {incidentQuery.data ? (
              <Panel title="Incident" density="compact">
                <p className="text-sm font-medium">{incidentQuery.data.title}</p>
                <Badge className="mt-2">{incidentQuery.data.state}</Badge>
                <p className="mt-2 font-mono text-xs text-[var(--aegis-text-muted)]">
                  {incidentQuery.data.id}
                </p>
              </Panel>
            ) : null}

            {incidentsQuery.data && incidentsQuery.data.length > 0 ? (
              <Panel title="Incidents" density="compact">
                <ul className="flex flex-col gap-2">
                  {incidentsQuery.data.map((incident) => (
                    <li key={incident.id}>
                      <button
                        type="button"
                        className="w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-left text-sm hover:bg-[var(--aegis-surface-elevated)]"
                        onClick={() => {
                          setSelectedEntityId(incident.id);
                        }}
                        aria-pressed={selectedEntityId === incident.id}
                      >
                        {incident.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}

            {alertsQuery.data && alertsQuery.data.length > 0 ? (
              <Panel title="Alerts" density="compact" data-testid="alerts-panel">
                <ul className="flex flex-col gap-2">
                  {alertsQuery.data.map((alert) => (
                    <li
                      key={alert.id}
                      className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2 text-sm"
                      data-testid={`alert-item-${alert.id}`}
                    >
                      <p className="font-medium">{alert.title}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Badge>{alert.severity}</Badge>
                        {alert.confidence != null ? (
                          <span className="text-xs text-[var(--aegis-text-muted)]">
                            {Math.round(alert.confidence * 100)}% confidence
                          </span>
                        ) : null}
                        {alert.detectorVersion ? (
                          <span className="font-mono text-xs text-[var(--aegis-text-muted)]">
                            {alert.detectorVersion}
                          </span>
                        ) : null}
                      </div>
                      {alert.explanation ? (
                        <details className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
                          <summary className="cursor-pointer">Explanation</summary>
                          <p className="mt-1">{alert.explanation.summary}</p>
                          <p className="mt-1 font-mono text-[10px]">
                            {alert.explanation.comparison}
                          </p>
                          {alert.evidence ? (
                            <p className="mt-1 text-[var(--aegis-text-muted)]">
                              Window: {alert.evidence.windowKey}
                            </p>
                          ) : null}
                        </details>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}

            {!selectedEntityId &&
            !incidentQuery.data &&
            (!incidentsQuery.data || incidentsQuery.data.length === 0) &&
            (!alertsQuery.data || alertsQuery.data.length === 0) ? (
              <EmptyState
                title="No selection"
                description="Select a graph node, incident, or alert to inspect evidence and context."
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
