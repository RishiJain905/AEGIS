'use client';

import { useState } from 'react';

import type {
  ActionProposalV1,
  PolicyDecisionV1,
  ProposalRevisionV1,
} from '@aegis/contracts-ts';
import { Alert, Button } from '@aegis/ui';

import {
  newApprovalIdempotencyKey,
  useApprovalMutations,
} from '@/features/approval/use-approval-mutations';
import { ApiClientError } from '@/lib/api/types';

export interface ApprovalControlsProps {
  incidentId: string;
  proposal: ActionProposalV1;
  revision: ProposalRevisionV1 | undefined;
  latestDecision: PolicyDecisionV1 | undefined;
}

export function ApprovalControls({
  incidentId,
  proposal,
  revision,
  latestDecision,
}: ApprovalControlsProps) {
  const { approve, reject, modify } = useApprovalMutations(incidentId);
  const [comment, setComment] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [modifyRationale, setModifyRationale] = useState(revision?.rationale ?? '');
  const [modifyTradeoffs, setModifyTradeoffs] = useState(revision?.riskTradeoffs ?? '');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const awaitingApproval =
    proposal.status === 'pending' && latestDecision?.outcome === 'approval_required';
  const busy = approve.isPending || reject.isPending || modify.isPending;

  if (!awaitingApproval || revision == null) {
    return null;
  }

  const baseFields = {
    schemaVersion: 1 as const,
    proposalId: proposal.id,
    expectedRevisionId: proposal.currentRevisionId ?? revision.id,
    expectedRevision: proposal.revision,
    actorId: 'asset:operator-console',
  };

  const handleError = (error: unknown) => {
    if (error instanceof ApiClientError) {
      setErrorMessage(`${error.code}: ${error.message}`);
      return;
    }
    setErrorMessage(error instanceof Error ? error.message : 'Approval request failed');
  };

  return (
    <div
      className="mt-3 space-y-3 border-t border-[var(--aegis-border-subtle)] pt-3"
      data-testid={`approval-controls-${proposal.id}`}
    >
      <p className="text-xs font-medium text-[var(--aegis-text-primary)]">
        Human approval required — decisions are enforced by the backend, not this UI.
      </p>
      <label className="block text-xs text-[var(--aegis-text-secondary)]">
        Operator comment
        <textarea
          className="mt-1 w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-transparent px-2 py-1 text-sm text-[var(--aegis-text-primary)]"
          rows={2}
          value={comment}
          onChange={(event) => {
            setComment(event.target.value);
          }}
          data-testid={`approval-comment-${proposal.id}`}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="default"
          disabled={busy}
          data-testid={`approve-proposal-${proposal.id}`}
          onClick={() => {
            setErrorMessage(null);
            setSuccessMessage(null);
            approve.mutate(
              {
                ...baseFields,
                comment,
                idempotencyKey: newApprovalIdempotencyKey('approve'),
              },
              {
                onSuccess: () => {
                  setSuccessMessage('Proposal approved and authorized command path recorded.');
                },
                onError: handleError,
              },
            );
          }}
        >
          Approve
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={busy || rejectReason.trim().length === 0}
          data-testid={`reject-proposal-${proposal.id}`}
          onClick={() => {
            setErrorMessage(null);
            setSuccessMessage(null);
            reject.mutate(
              {
                ...baseFields,
                reason: rejectReason,
                comment,
                idempotencyKey: newApprovalIdempotencyKey('reject'),
              },
              {
                onSuccess: () => {
                  setSuccessMessage('Proposal rejected; execution blocked.');
                },
                onError: handleError,
              },
            );
          }}
        >
          Reject
        </Button>
      </div>
      <label className="block text-xs text-[var(--aegis-text-secondary)]">
        Rejection reason
        <input
          className="mt-1 w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-transparent px-2 py-1 text-sm text-[var(--aegis-text-primary)]"
          value={rejectReason}
          onChange={(event) => {
            setRejectReason(event.target.value);
          }}
          data-testid={`reject-reason-${proposal.id}`}
        />
      </label>
      <details className="text-xs" data-testid={`modify-proposal-details-${proposal.id}`}>
        <summary className="cursor-pointer font-medium text-[var(--aegis-text-primary)]">
          Modify / request revision
        </summary>
        <div className="mt-2 space-y-2">
          <label className="block text-[var(--aegis-text-secondary)]">
            Revised rationale
            <textarea
              className="mt-1 w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-transparent px-2 py-1 text-sm text-[var(--aegis-text-primary)]"
              rows={2}
              value={modifyRationale}
              onChange={(event) => {
                setModifyRationale(event.target.value);
              }}
              data-testid={`modify-rationale-${proposal.id}`}
            />
          </label>
          <label className="block text-[var(--aegis-text-secondary)]">
            Risk tradeoffs
            <textarea
              className="mt-1 w-full rounded-[var(--aegis-radius-sm)] border border-[var(--aegis-border-subtle)] bg-transparent px-2 py-1 text-sm text-[var(--aegis-text-primary)]"
              rows={2}
              value={modifyTradeoffs}
              onChange={(event) => {
                setModifyTradeoffs(event.target.value);
              }}
              data-testid={`modify-tradeoffs-${proposal.id}`}
            />
          </label>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy || modifyRationale.trim().length === 0}
            data-testid={`modify-proposal-${proposal.id}`}
            onClick={() => {
              setErrorMessage(null);
              setSuccessMessage(null);
              modify.mutate(
                {
                  ...baseFields,
                  selectedOptionId: revision.selectedOptionId,
                  rationale: modifyRationale,
                  riskTradeoffs: modifyTradeoffs || revision.riskTradeoffs,
                  comment,
                  idempotencyKey: newApprovalIdempotencyKey('modify'),
                },
                {
                  onSuccess: () => {
                    setSuccessMessage('Proposal revised; WARDEN re-evaluation required.');
                  },
                  onError: handleError,
                },
              );
            }}
          >
            Submit modification
          </Button>
        </div>
      </details>
      {errorMessage ? (
        <Alert variant="error" title="Approval workflow error">
          <p data-testid={`approval-error-${proposal.id}`}>{errorMessage}</p>
        </Alert>
      ) : null}
      {successMessage ? (
        <Alert variant="success" title="Decision recorded">
          <p data-testid={`approval-success-${proposal.id}`}>{successMessage}</p>
        </Alert>
      ) : null}
    </div>
  );
}
