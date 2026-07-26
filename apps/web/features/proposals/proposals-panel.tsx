'use client';

import { useState } from 'react';

import type {
  ActionProposalV1,
  InvestigationDetailV1,
  PolicyDecisionV1,
  ProposalRevisionV1,
  ResponseOptionV1,
} from '@aegis/contracts-ts';
import { Alert, Badge, EmptyState, ErrorState, LoadingState, Panel } from '@aegis/ui';

import { ApprovalControls } from '@/features/approval/approval-controls';
import { BlastRadiusSummary, useBlastRadius } from '@/features/operator-actions';
import { useInvestigationDetail } from '@/features/investigation/use-investigation-queries';
import type { ScenarioCommandTemplate } from '@/features/command-surface';

export interface ProposalsPanelProps {
  incidentId: string;
}

function policyOutcomeVariant(
  outcome: PolicyDecisionV1['outcome'],
): 'info' | 'warning' | 'error' | 'success' {
  switch (outcome) {
    case 'allow':
      return 'success';
    case 'approval_required':
      return 'warning';
    case 'block':
      return 'error';
    default: {
      const _exhaustive: never = outcome;
      throw new Error(`Unhandled policy outcome: ${String(_exhaustive)}`);
    }
  }
}

function selectedOption(revision: ProposalRevisionV1 | undefined): ResponseOptionV1 | undefined {
  if (!revision) {
    return undefined;
  }
  return revision.responseOptions.find((option) => option.optionId === revision.selectedOptionId);
}

function ProposalCard({
  incidentId,
  runId,
  proposal,
  revision,
  decisions,
}: {
  incidentId: string;
  runId: string;
  proposal: ActionProposalV1;
  revision: ProposalRevisionV1 | undefined;
  decisions: PolicyDecisionV1[];
}) {
  const option = selectedOption(revision);
  const latestDecision = decisions.filter((decision) => decision.proposalId === proposal.id).at(-1);

  // Blast-radius preview for the same Class 2/3 containment the approver is about to allow.
  const isContainment = proposal.actionClass === 'class_2' || proposal.actionClass === 'class_3';
  const targetAssetId = option?.targetAssetId ?? proposal.targetAssetId;
  const scenarioCommand = (option?.scenarioCommand ??
    proposal.scenarioCommand) as ScenarioCommandTemplate | null;
  const blastRadius = useBlastRadius(
    runId,
    isContainment ? scenarioCommand : null,
    isContainment ? targetAssetId : null,
    { enabled: isContainment && Boolean(scenarioCommand) },
  );

  return (
    <li
      className="rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] px-3 py-2"
      data-testid={`proposal-card-${proposal.id}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{proposal.actionClass}</Badge>
        <Badge>{proposal.status}</Badge>
        {proposal.scenarioCommand ? <Badge>{proposal.scenarioCommand}</Badge> : null}
      </div>
      <p className="mt-2 text-sm">{proposal.rationale}</p>
      {revision ? (
        <p className="mt-2 text-xs text-[var(--aegis-text-secondary)]">
          <span className="font-medium text-[var(--aegis-text-primary)]">Risk tradeoffs:</span>{' '}
          {revision.riskTradeoffs}
        </p>
      ) : null}
      {option ? (
        <div className="mt-3 space-y-2 text-xs text-[var(--aegis-text-secondary)]">
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">Expected benefit:</span>{' '}
            {option.expectedBenefit}
          </p>
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">Operational cost:</span>{' '}
            {option.operationalCost}
          </p>
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">Reversibility:</span>{' '}
            {option.reversibility}
          </p>
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">Affected assets:</span>{' '}
            {[option.targetAssetId, ...option.affectedAssetIds].join(', ')}
          </p>
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">
              Expected consequences:
            </span>{' '}
            {option.expectedConsequences}
          </p>
          <p>
            <span className="font-medium text-[var(--aegis-text-primary)]">Uncertainty:</span>{' '}
            {option.uncertainty} ({Math.round(option.confidence * 100)}% confidence)
          </p>
          <details>
            <summary className="cursor-pointer">Evidence & monitoring</summary>
            <p className="mt-1">Evidence: {option.evidenceIds.join(', ')}</p>
            <p className="mt-1">Hypotheses: {option.hypothesisIds.join(', ')}</p>
            <p className="mt-1">Monitoring: {option.monitoringPlan}</p>
          </details>
        </div>
      ) : null}
      {latestDecision ? (
        <div
          className="mt-3"
          data-testid={`policy-result-${proposal.id}`}
          data-tutorial-id="warden-decision"
        >
          <Alert
            variant={policyOutcomeVariant(latestDecision.outcome)}
            title={`WARDEN: ${latestDecision.outcome}`}
          >
            <p>{latestDecision.reasonCodes.join(', ')}</p>
            {latestDecision.explanationProse ? (
              <p className="mt-1 text-xs">{latestDecision.explanationProse}</p>
            ) : null}
            {latestDecision.approvalRequirement?.required ? (
              <p className="mt-2 text-xs font-medium">
                Human approval required — approvers:{' '}
                {latestDecision.approvalRequirement.approverRoles.join(', ')}
              </p>
            ) : null}
          </Alert>
        </div>
      ) : null}
      {isContainment && scenarioCommand ? (
        <div className="mt-3">
          <BlastRadiusSummary
            preview={blastRadius.data}
            loading={blastRadius.isLoading}
            error={blastRadius.isError}
          />
        </div>
      ) : null}
      <ApprovalControls
        incidentId={incidentId}
        proposal={proposal}
        revision={revision}
        latestDecision={latestDecision}
      />
    </li>
  );
}

function ProposalsContent({
  incidentId,
  detail,
}: {
  incidentId: string;
  detail: InvestigationDetailV1;
}) {
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(
    detail.proposals[0]?.id ?? null,
  );

  if (detail.proposals.length === 0) {
    return (
      <EmptyState
        title="No response proposals"
        description="BASTION proposals appear after ORACLE hypotheses are available."
      />
    );
  }

  const revisionsByProposal = new Map(
    detail.proposalRevisions.map((revision) => [revision.proposalId, revision]),
  );
  const decisionsByProposal = detail.policyDecisions.reduce<Map<string, PolicyDecisionV1[]>>(
    (acc, decision) => {
      const existing = acc.get(decision.proposalId) ?? [];
      existing.push(decision);
      acc.set(decision.proposalId, existing);
      return acc;
    },
    new Map(),
  );

  return (
    <div className="flex flex-col gap-3">
      <Panel title="BASTION response proposals" density="compact" data-testid="proposals-panel">
        <ul className="flex flex-col gap-3">
          {detail.proposals.map((proposal) => (
            <button
              key={proposal.id}
              type="button"
              className="text-left"
              onClick={() => {
                setSelectedProposalId(proposal.id);
              }}
              aria-pressed={selectedProposalId === proposal.id}
            >
              <ProposalCard
                incidentId={incidentId}
                runId={detail.runId}
                proposal={proposal}
                revision={revisionsByProposal.get(proposal.id)}
                decisions={decisionsByProposal.get(proposal.id) ?? []}
              />
            </button>
          ))}
        </ul>
      </Panel>
      <Panel
        title="Proposal lifecycle & audit"
        density="compact"
        data-testid="proposal-lifecycle-panel"
      >
        <ul className="space-y-2 text-xs text-[var(--aegis-text-secondary)]">
          {detail.proposals.map((proposal) => (
            <li key={`audit-${proposal.id}`} className="font-mono">
              {proposal.id} · status={proposal.status} · revision={proposal.revision}
            </li>
          ))}
          {detail.policyDecisions.map((decision) => (
            <li key={decision.id} className="font-mono">
              policy {decision.id} · {decision.outcome} · {decision.evaluatedAt}
            </li>
          ))}
          {detail.approvals.map((approval) => (
            <li
              key={approval.id}
              className="font-mono"
              data-testid={`approval-audit-${approval.id}`}
            >
              approval {approval.id} · {approval.decision} · {approval.approverId} ·{' '}
              {approval.decidedAt}
            </li>
          ))}
          {detail.executedActions.map((action) => (
            <li key={action.id} className="font-mono" data-testid={`execution-audit-${action.id}`}>
              executed {action.id} · proposal={action.proposalId} · {action.executedAt}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

export function ProposalsPanel({ incidentId }: ProposalsPanelProps) {
  const query = useInvestigationDetail(incidentId);

  if (query.isPending) {
    return <LoadingState message="Loading proposals…" />;
  }
  const detail = query.data;
  if (query.isError || detail == null) {
    return (
      <ErrorState
        title="Failed to load proposals"
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }

  return <ProposalsContent incidentId={incidentId} detail={detail} />;
}
