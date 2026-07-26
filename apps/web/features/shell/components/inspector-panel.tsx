'use client';

import { Badge, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

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

/**
 * Evidence and context for the current selection. It is dock content now, not a panel with
 * its own chrome: the run workspace's right dock owns the frame, header and collapse, and
 * commanding the selected asset moved out to the stage command bar where the operator is
 * already looking.
 */
export function InspectorPanel({ runId, incidentId }: InspectorPanelProps) {
  const selectedEntityId = useWorkspaceUiStore((state) => state.workspace.selectedEntityId);
  const setSelectedEntityId = useWorkspaceUiStore((state) => state.setSelectedEntityId);

  const incidentQuery = useIncident(incidentId ?? '');
  const incidentsQuery = useRunIncidents(runId ?? '');
  const alertsQuery = useRunAlerts(runId ?? '');
  const riskScoresQuery = useRunRiskScores(runId ?? '');
  const graphQuery = useRunGraph(runId ?? '');

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
    <div className="flex min-w-0 flex-col" data-testid="inspector-panel">
      <div>
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
    </div>
  );
}
