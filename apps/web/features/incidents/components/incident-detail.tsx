'use client';

import Link from 'next/link';
import { useEffect, useMemo } from 'react';

import type { AlertV1 } from '@aegis/contracts-ts';
import { Button, Card, EmptyState, ErrorState, LoadingState, MetricTile, Panel } from '@aegis/ui';

import { isNotFoundError } from '@/lib/api';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import {
  useIncident,
  useIncidentRunAlerts,
  useInvestigationDetail,
} from '../hooks/use-incident-queries';
import {
  buildAgentRoster,
  buildProposalViews,
  buildTriageTimeline,
  formatRelativeAge,
  getIncidentStatePresentation,
  getNextAction,
  maxSeverity,
} from '../lib/incident-model';
import { IncidentAgentRoster } from './incident-agent-roster';
import { IncidentAlertsEvidence } from './incident-alerts-evidence';
import { IncidentProposals } from './incident-proposals';
import { IncidentStateBadge, MetaItem, SeverityChip } from './incident-primitives';
import { IncidentTriageTimeline } from './incident-triage-timeline';
import { IncidentWorkspace } from './incident-workspace';

const BackToQueue = (
  <Button asChild variant="outline" size="sm">
    <Link href="/incidents">All incidents</Link>
  </Button>
);

export function IncidentDetail({ incidentId }: { incidentId: string }) {
  const incidentQuery = useIncident(incidentId);
  const runId = incidentQuery.data?.runId;
  const alertsQuery = useIncidentRunAlerts(runId);
  const investigationQuery = useInvestigationDetail(incidentId);
  const resetForRun = useWorkspaceUiStore((state) => state.resetForRun);

  // Keep cross-navigation (Active run / Reports / After-action) pointed at the
  // run that owns this incident.
  useEffect(() => {
    if (runId) {
      resetForRun(runId);
    }
  }, [runId, resetForRun]);

  const incident = incidentQuery.data;
  const investigation = investigationQuery.isSuccess ? investigationQuery.data : null;

  const linkedAlerts = useMemo<AlertV1[]>(() => {
    if (!incident || !alertsQuery.data) {
      return [];
    }
    const linkedIds = new Set(incident.alertIds);
    return alertsQuery.data.filter((alert) => linkedIds.has(alert.id));
  }, [incident, alertsQuery.data]);

  const timeline = useMemo(
    () => (incident ? buildTriageTimeline(incident, linkedAlerts, investigation) : []),
    [incident, linkedAlerts, investigation],
  );
  const roster = useMemo(() => buildAgentRoster(investigation), [investigation]);
  const proposalViews = useMemo(() => buildProposalViews(investigation), [investigation]);

  if (incidentQuery.isPending) {
    return (
      <IncidentWorkspace eyebrow="Incident" title="Loading incident…" actions={BackToQueue}>
        <LoadingState message="Loading incident…" data-testid="incident-detail-loading" />
      </IncidentWorkspace>
    );
  }

  if (incidentQuery.isError || !incident) {
    const notFound = isNotFoundError(incidentQuery.error);
    return (
      <IncidentWorkspace eyebrow="Incident" title="Incident unavailable" actions={BackToQueue}>
        {notFound ? (
          <EmptyState
            title="Incident not found"
            description={`No incident matches ${incidentId}.`}
            data-testid="incident-detail-notfound"
          />
        ) : (
          <ErrorState
            message="Unable to load this incident."
            onRetry={() => void incidentQuery.refetch()}
            data-testid="incident-detail-error"
          />
        )}
      </IncidentWorkspace>
    );
  }

  const presentation = getIncidentStatePresentation(incident.state);
  const severity = maxSeverity(linkedAlerts);
  const pendingProposals = proposalViews.filter((v) => v.proposal.status === 'pending').length;
  const evidence = investigation?.evidenceAttachments ?? [];
  const candidateAssets = investigation?.candidateAssets ?? [];

  const actions = (
    <>
      {BackToQueue}
      {runId ? (
        <Button asChild variant="ghost" size="sm">
          <Link href={`/runs/${encodeURIComponent(runId)}`}>Open run graph</Link>
        </Button>
      ) : null}
    </>
  );

  return (
    <IncidentWorkspace
      eyebrow="Incident"
      title={incident.title}
      description={getNextAction(incident.state)}
      actions={actions}
    >
      <Panel data-testid="incident-detail-summary">
        <div className="flex flex-wrap items-center gap-3">
          <IncidentStateBadge state={incident.state} />
          <SeverityChip severity={severity} />
          <span className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--aegis-text-muted)]">
            {presentation.phase}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
          <MetaItem label="Incident">
            <span className="font-mono text-xs">{incident.id}</span>
          </MetaItem>
          <MetaItem label="Run">
            <span className="font-mono text-xs">{incident.runId}</span>
          </MetaItem>
          <MetaItem label="Opened">{formatRelativeAge(incident.createdAt)} ago</MetaItem>
          <MetaItem label="Updated">{formatRelativeAge(incident.updatedAt)} ago</MetaItem>
          <MetaItem label="Linked alerts">{incident.alertIds.length}</MetaItem>
          <MetaItem label="Pending approvals">{pendingProposals}</MetaItem>
        </div>
      </Panel>

      <div className="grid min-h-0 grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="flex flex-col gap-5 xl:col-span-2">
          <IncidentTriageTimeline events={timeline} />
          <IncidentProposals views={proposalViews} />
          <IncidentAlertsEvidence alerts={linkedAlerts} evidence={evidence} />
        </div>
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-3">
            <MetricTile label="Evidence" value={evidence.length} />
            <MetricTile label="Proposals" value={proposalViews.length} />
          </div>
          <IncidentAgentRoster roster={roster} />
          <Panel title="Candidate affected assets" density="compact">
            {candidateAssets.length === 0 ? (
              <p className="text-xs text-[var(--aegis-text-muted)]">
                No candidate assets identified yet.
              </p>
            ) : (
              <ul className="flex flex-col gap-2" role="list">
                {candidateAssets.map((asset) => (
                  <li key={asset.id} className="text-xs">
                    <span className="font-mono text-[var(--aegis-text-primary)]">
                      {asset.assetId}
                    </span>
                    <span className="ml-2 text-[var(--aegis-text-muted)] tabular-nums">
                      {(asset.confidence * 100).toFixed(0)}%
                    </span>
                    <p className="mt-0.5 leading-5 text-[var(--aegis-text-secondary)]">
                      {asset.rationale}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {runId ? (
            <Card
              title="SCRIBE after-action report"
              description="Narrative report generated once the incident is resolved."
            >
              <Button asChild variant="secondary" size="sm">
                <Link href={`/after-action/${encodeURIComponent(runId)}`}>
                  Open after-action report
                </Link>
              </Button>
            </Card>
          ) : null}
        </div>
      </div>
    </IncidentWorkspace>
  );
}
