'use client';

import { Badge, EmptyState, Panel, cn } from '@aegis/ui';

import { ApprovalControls } from '@/features/approval/approval-controls';

import type { ProposalView } from '../lib/incident-model';

function statusTone(status: string): string {
  switch (status) {
    case 'approved':
    case 'executed':
      return 'text-[var(--aegis-status-contained)]';
    case 'rejected':
    case 'cancelled':
      return 'text-[var(--aegis-status-compromised)]';
    default:
      return 'text-[var(--aegis-status-suspicious)]';
  }
}

function ApprovalState({ view }: { view: ProposalView }) {
  if (view.executed) {
    return <span className="text-[var(--aegis-status-contained)]">Executed</span>;
  }
  if (view.approval) {
    return (
      <span className={statusTone(view.approval.decision)}>
        {view.approval.decision === 'approved' ? 'Approved' : 'Rejected'} by{' '}
        {view.approval.approverId}
      </span>
    );
  }
  if (view.policy?.approvalRequirement?.required) {
    return <span className="text-[var(--aegis-status-suspicious)]">Awaiting human approval</span>;
  }
  if (view.policy?.outcome === 'block') {
    return <span className="text-[var(--aegis-status-compromised)]">Blocked by policy</span>;
  }
  if (view.policy?.outcome === 'allow') {
    return <span className="text-[var(--aegis-status-contained)]">Policy-allowed</span>;
  }
  return <span className="text-[var(--aegis-text-muted)]">Pending evaluation</span>;
}

export function IncidentProposals({
  incidentId,
  views,
}: {
  incidentId: string;
  views: readonly ProposalView[];
}) {
  const pending = views.filter((view) => view.proposal.status === 'pending').length;

  return (
    <Panel
      title="Response proposals"
      description={
        pending > 0
          ? `${String(pending)} proposal${pending === 1 ? '' : 's'} awaiting approval.`
          : 'Proposed containment actions and their approval state.'
      }
      data-testid="incident-proposals"
    >
      {views.length === 0 ? (
        <EmptyState
          title="No proposals"
          description="No response actions have been proposed for this incident."
        />
      ) : (
        <ul className="-m-5 divide-y divide-[var(--aegis-border-subtle)]" role="list">
          {views.map((view) => (
            <li
              key={view.proposal.id}
              className={cn(
                'relative px-5 py-4',
                view.proposal.status === 'pending' ? 'bg-[var(--aegis-surface-raised)]/40' : '',
              )}
              data-testid={`proposal-${view.proposal.id}`}
            >
              {view.proposal.status === 'pending' ? (
                <span
                  aria-hidden="true"
                  className="absolute inset-y-0 left-0 w-[3px] bg-[var(--aegis-status-suspicious)]"
                />
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-[family-name:var(--aegis-font-display)] text-sm font-semibold tracking-[0.01em] text-[var(--aegis-text-primary)]">
                  {view.proposal.command}
                </span>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{view.proposal.actionClass.replace('_', ' ')}</Badge>
                  <span
                    className={cn(
                      'font-[family-name:var(--aegis-font-mono)] text-[0.625rem] uppercase tracking-[0.08em]',
                      statusTone(view.proposal.status),
                    )}
                  >
                    {view.proposal.status}
                  </span>
                </div>
              </div>
              <p className="mt-1 font-[family-name:var(--aegis-font-mono)] text-[0.625rem] text-[var(--aegis-text-muted)]">
                {view.proposal.targetAssetId}
              </p>
              {view.proposal.rationale ? (
                <p className="mt-1.5 text-xs leading-5 text-[var(--aegis-text-secondary)]">
                  {view.proposal.rationale}
                </p>
              ) : null}
              <p className="mt-2.5 border-t border-[var(--aegis-border-subtle)] pt-2.5 text-xs">
                <ApprovalState view={view} />
              </p>
              {/*
                Interactive human-approval gate. ApprovalControls renders the
                approve/reject/modify actions only for a PENDING proposal that
                carries an `approval_required` policy decision and its current
                revision, and only for an actor holding `approvals:decide`
                (server remains authoritative). For already-decided proposals it
                renders nothing, leaving the read-only status above intact.
              */}
              <ApprovalControls
                incidentId={incidentId}
                proposal={view.proposal}
                revision={view.revision ?? undefined}
                latestDecision={view.policy ?? undefined}
              />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
