import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiClientError } from '@/lib/api/types';

import type { ProposalView } from '../lib/incident-model';

const { approveMutate, rejectMutate, modifyMutate, authState } = vi.hoisted(() => ({
  approveMutate: vi.fn(),
  rejectMutate: vi.fn(),
  modifyMutate: vi.fn(),
  authState: { canDecide: true },
}));

// The incident approval gate reuses the shared ApprovalControls, which reads the
// auth context and the approval mutations. Stub both so this test exercises the
// component wiring (gating + payload) without a live QueryClient/AuthProvider.
vi.mock('@/features/auth', () => ({
  useAuth: () => ({ hasPermission: () => authState.canDecide }),
}));

vi.mock('@/features/approval/use-approval-mutations', () => ({
  useApprovalMutations: () => ({
    approve: { isPending: false, mutate: approveMutate },
    reject: { isPending: false, mutate: rejectMutate },
    modify: { isPending: false, mutate: modifyMutate },
  }),
  newApprovalIdempotencyKey: (prefix: string) => `${prefix}-test-key`,
}));

import { IncidentProposals } from './incident-proposals';

const INCIDENT_ID = 'incident:inc_synthetic_001';

// A PENDING class-2 isolate carrying an approval_required policy decision plus its
// current revision — the shape the interactive gate requires.
const pendingView = {
  proposal: {
    id: 'prp_pending',
    status: 'pending',
    command: 'isolate',
    actionClass: 'class_2',
    targetAssetId: 'asset:svc-api-gateway',
    rationale: 'Isolate the gateway to contain suspected credential abuse.',
    currentRevisionId: 'prv_pending',
    revision: 3,
  },
  revision: {
    id: 'prv_pending',
    selectedOptionId: 'opt-isolate',
    rationale: 'Isolation balances containment against operational cost.',
    riskTradeoffs: 'May disrupt internal consumers; delay risks lateral movement.',
  },
  policy: {
    proposalId: 'prp_pending',
    outcome: 'approval_required',
    approvalRequirement: { required: true, approverRoles: ['security_lead'] },
  },
  approval: null,
  executed: null,
} as unknown as ProposalView;

// An already-decided (approved) proposal — must stay read-only, no controls.
const decidedView = {
  proposal: {
    id: 'prp_decided',
    status: 'approved',
    command: 'observe',
    actionClass: 'class_0',
    targetAssetId: 'asset:svc-api-gateway',
    rationale: 'Continue observation without disruption.',
    currentRevisionId: 'prv_decided',
    revision: 1,
  },
  revision: {
    id: 'prv_decided',
    selectedOptionId: 'opt-observe',
    rationale: 'Low-impact monitoring.',
    riskTradeoffs: 'Slower containment if the hypothesis holds.',
  },
  policy: { proposalId: 'prp_decided', outcome: 'allow' },
  approval: { proposalId: 'prp_decided', decision: 'approved', approverId: 'user:operator-alpha' },
  executed: null,
} as unknown as ProposalView;

describe('IncidentProposals interactive approval gate', () => {
  beforeEach(() => {
    approveMutate.mockReset();
    rejectMutate.mockReset();
    modifyMutate.mockReset();
    authState.canDecide = true;
  });
  afterEach(() => {
    cleanup();
  });

  it('renders approve/reject/modify controls for a pending proposal to an authorized actor', () => {
    render(<IncidentProposals incidentId={INCIDENT_ID} views={[pendingView, decidedView]} />);

    expect(screen.getByTestId('approve-proposal-prp_pending')).toBeInTheDocument();
    expect(screen.getByTestId('reject-proposal-prp_pending')).toBeInTheDocument();
    expect(screen.getByTestId('modify-proposal-prp_pending')).toBeInTheDocument();

    // Already-decided proposals keep their read-only status and expose no controls.
    const decided = screen.getByTestId('proposal-prp_decided');
    expect(within(decided).getByText(/Approved by user:operator-alpha/)).toBeInTheDocument();
    expect(screen.queryByTestId('approve-proposal-prp_decided')).not.toBeInTheDocument();
    expect(screen.queryByTestId('approval-controls-readonly-prp_decided')).not.toBeInTheDocument();
  });

  it('renders a read-only notice (no action buttons) for an unauthorized actor', () => {
    authState.canDecide = false;
    render(<IncidentProposals incidentId={INCIDENT_ID} views={[pendingView]} />);

    expect(screen.getByTestId('approval-controls-readonly-prp_pending')).toBeInTheDocument();
    expect(screen.queryByTestId('approve-proposal-prp_pending')).not.toBeInTheDocument();
    expect(screen.queryByTestId('reject-proposal-prp_pending')).not.toBeInTheDocument();
  });

  it('invokes the approval mutation with the idempotency key and stale-revision guard, and reflects success', () => {
    render(<IncidentProposals incidentId={INCIDENT_ID} views={[pendingView]} />);

    fireEvent.click(screen.getByTestId('approve-proposal-prp_pending'));

    expect(approveMutate).toHaveBeenCalledTimes(1);
    const [payload, callbacks] = approveMutate.mock.calls[0] as [
      Record<string, unknown>,
      { onSuccess: () => void; onError: (error: unknown) => void },
    ];
    expect(payload).toMatchObject({
      proposalId: 'prp_pending',
      // Stale-state guard: the current revision id + revision number are sent so the
      // server can reject a decision made against an outdated proposal.
      expectedRevisionId: 'prv_pending',
      expectedRevision: 3,
      idempotencyKey: 'approve-test-key',
    });

    act(() => {
      callbacks.onSuccess();
    });
    expect(screen.getByTestId('approval-success-prp_pending')).toBeInTheDocument();
  });

  it('surfaces a stale-proposal conflict returned by the approvals API', () => {
    render(<IncidentProposals incidentId={INCIDENT_ID} views={[pendingView]} />);

    fireEvent.click(screen.getByTestId('approve-proposal-prp_pending'));
    const [, callbacks] = approveMutate.mock.calls[0] as [
      Record<string, unknown>,
      { onSuccess: () => void; onError: (error: unknown) => void },
    ];

    act(() => {
      callbacks.onError(
        new ApiClientError({
          code: 'STALE_PROPOSAL',
          message: 'Proposal revision changed',
          status: 409,
        }),
      );
    });

    expect(screen.getByTestId('approval-error-prp_pending')).toHaveTextContent('STALE_PROPOSAL');
  });
});
