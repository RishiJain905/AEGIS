'use client';

import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  cn,
  typographyTokens,
} from '@aegis/ui';

import {
  GraphEntityInspector,
  IncidentContextInspector,
  InspectorLabel,
  InspectorMonoValue,
} from '@/features/inspector';
import { InvestigationPanel } from '@/features/investigation';
import { ProposalsPanel } from '@/features/proposals/proposals-panel';
import { ReportsPanel } from '@/features/reports/reports-panel';
import { RiskExplanationPanel } from '@/features/risk';
import {
  useIncident,
  useRunAlerts,
  useRunGraph,
  useRunIncidents,
  useRunRiskScores,
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
  const riskScoresQuery = useRunRiskScores(runId ?? '');
  const graphQuery = useRunGraph(runId ?? '');

  if (collapsed) {
    return (
      <div className="flex w-14 shrink-0 flex-col items-center rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-rail)] p-2 shadow-[var(--aegis-shadow-panel)]">
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
    (runId &&
      (incidentsQuery.isPending ||
        alertsQuery.isPending ||
        riskScoresQuery.isPending ||
        graphQuery.isPending));
  const isError =
    (incidentId && incidentQuery.isError) ||
    (runId &&
      (incidentsQuery.isError ||
        alertsQuery.isError ||
        riskScoresQuery.isError ||
        graphQuery.isError));

  const snapshot = graphQuery.data?.snapshot ?? null;
  const selectedRiskScore =
    riskScoresQuery.data?.find((score) => score.assetId === selectedEntityId) ?? null;
  const selectedAlert = alertsQuery.data?.find((alert) => alert.assetId === selectedEntityId);

  return (
    <aside
      className="flex w-full shrink-0 flex-col overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-default)] bg-[var(--aegis-surface-panel)] shadow-[var(--aegis-shadow-panel)] lg:w-80 xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)] xl:w-96"
      data-testid="inspector-panel"
      aria-label="Inspector"
    >
      <div className="flex items-center justify-between border-b border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-4 py-3">
        <div>
          <p className={cn(typographyTokens.eyebrow, 'text-[var(--aegis-text-muted)]')}>
            Context channel
          </p>
          <h2 className={cn(typographyTokens.displayMd, 'text-[var(--aegis-text-primary)]')}>
            Inspector
          </h2>
        </div>
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
              void riskScoresQuery.refetch();
              void graphQuery.refetch();
            }}
          />
        ) : null}

        {!isLoading && !isError ? (
          <div className="flex flex-col gap-4">
            {snapshot ? (
              <GraphEntityInspector
                snapshot={snapshot}
                selectedEntityId={selectedEntityId}
                riskScore={selectedRiskScore}
              />
            ) : null}

            <RiskExplanationPanel
              riskScore={selectedRiskScore}
              directDetectionScore={selectedAlert?.confidence ?? null}
            />

            {incidentsQuery.data && alertsQuery.data ? (
              <IncidentContextInspector
                incidents={incidentsQuery.data}
                alerts={alertsQuery.data}
                selectedEntityId={selectedEntityId}
              />
            ) : null}

            {incidentId ? <InvestigationPanel incidentId={incidentId} /> : null}
            {incidentId ? <ProposalsPanel incidentId={incidentId} /> : null}
            {runId ? <ReportsPanel runId={runId} /> : null}

            {incidentQuery.data ? (
              <Panel title="Incident" density="compact">
                <div className="flex flex-col gap-3">
                  <p className="text-sm font-semibold leading-5 text-[var(--aegis-text-primary)]">
                    {incidentQuery.data.title}
                  </p>
                  <Badge className="self-start">{incidentQuery.data.state}</Badge>
                  <div className="flex flex-col gap-1">
                    <InspectorLabel>Incident ID</InspectorLabel>
                    <InspectorMonoValue value={incidentQuery.data.id} />
                  </div>
                </div>
              </Panel>
            ) : null}

            {incidentsQuery.data && incidentsQuery.data.length > 0 ? (
              <Panel title="Incidents" density="compact">
                <ul className="flex flex-col gap-2">
                  {incidentsQuery.data.map((incident) => (
                    <li key={incident.id}>
                      <button
                        type="button"
                        className="min-h-10 w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-elevated)] px-3 py-2 text-left text-sm transition-[background-color,border-color,color] hover:border-[var(--aegis-border-strong)] hover:bg-[var(--aegis-surface-hover)] aria-pressed:border-[var(--aegis-accent-line)] aria-pressed:text-[var(--aegis-accent-strong)]"
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
                      className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] border-l-[3px] border-l-[var(--aegis-risk-high)] bg-[var(--aegis-surface-elevated)] px-3 py-3 text-sm shadow-[var(--aegis-shadow-control)]"
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
                        <details className="mt-2 text-xs leading-5 text-[var(--aegis-text-secondary)]">
                          <summary className="cursor-pointer font-medium">Explanation</summary>
                          <p className="mt-1.5 break-words">{alert.explanation.summary}</p>
                          <p className="mt-1.5 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
                            {alert.explanation.comparison}
                          </p>
                          {alert.evidence ? (
                            <p className="mt-1.5 break-words text-[var(--aegis-text-muted)]">
                              Window: {alert.evidence.windowKey}
                            </p>
                          ) : null}
                        </details>
                      ) : null}
                      {'anomalyExplanation' in alert && alert.anomalyExplanation ? (
                        <details
                          className="mt-2 text-xs leading-5 text-[var(--aegis-text-secondary)]"
                          open={alert.detectorId === 'isolation-forest'}
                        >
                          <summary className="cursor-pointer font-medium">Anomaly model</summary>
                          <p className="mt-1.5 break-words">
                            {(alert.anomalyExplanation as { summary?: string }).summary}
                          </p>
                          <p className="mt-1.5 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
                            Score:{' '}
                            {(
                              (
                                alert.anomalyExplanation as {
                                  observedScore?: number;
                                }
                              ).observedScore ??
                              alert.confidence ??
                              0
                            ).toFixed(2)}{' '}
                            / threshold{' '}
                            {(
                              alert.anomalyExplanation as { threshold?: number }
                            ).threshold?.toFixed(2)}
                          </p>
                          {'modelVersionId' in alert && alert.modelVersionId ? (
                            <p className="mt-1.5 break-words font-mono text-[10px] leading-4 text-[var(--aegis-text-muted)]">
                              Model: {String(alert.modelVersionId)}
                            </p>
                          ) : null}
                          {(
                            alert.anomalyExplanation as {
                              topFeatures?: string[];
                            }
                          ).topFeatures ? (
                            <p className="mt-1.5 break-words text-[var(--aegis-text-muted)]">
                              Top features:{' '}
                              {(
                                (
                                  alert.anomalyExplanation as {
                                    topFeatures?: string[];
                                  }
                                ).topFeatures ?? []
                              ).join(', ')}
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
