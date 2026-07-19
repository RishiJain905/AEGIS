import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useIncident, useIncidentRunAlerts, useInvestigationDetail } = vi.hoisted(() => ({
  useIncident: vi.fn(),
  useIncidentRunAlerts: vi.fn(),
  useInvestigationDetail: vi.fn(),
}));

vi.mock('@/features/incidents/hooks/use-incident-queries', () => ({
  useIncident,
  useIncidentRunAlerts,
  useInvestigationDetail,
}));

vi.mock('@/features/incidents/components/incident-workspace', () => ({
  IncidentWorkspace: ({
    children,
    title,
    actions,
  }: {
    children: React.ReactNode;
    title: string;
    actions?: React.ReactNode;
  }) => (
    <div data-testid="workspace-mock">
      <h1>{title}</h1>
      {actions}
      {children}
    </div>
  ),
}));

vi.mock('@/stores/workspace-ui-store', () => ({
  useWorkspaceUiStore: (selector: (s: { resetForRun: () => void }) => unknown) =>
    selector({ resetForRun: () => {} }),
}));

vi.mock('@/lib/api', () => ({ isNotFoundError: () => false }));

// The incident proposals section now mounts the interactive ApprovalControls,
// which read the auth context and the approval mutations. Stub both so the
// detail render stays a pure incident-shape assertion (a VIEWER without
// approvals:decide) — the interactive path has its own dedicated test.
vi.mock('@/features/auth', () => ({
  useAuth: () => ({ hasPermission: () => false }),
}));

vi.mock('@/features/approval/use-approval-mutations', () => ({
  useApprovalMutations: () => ({
    approve: { isPending: false, mutate: vi.fn() },
    reject: { isPending: false, mutate: vi.fn() },
    modify: { isPending: false, mutate: vi.fn() },
  }),
  newApprovalIdempotencyKey: (prefix: string) => `${prefix}-test`,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { IncidentDetail } from '@/features/incidents/components/incident-detail';

const incident = {
  id: 'incident:inc_1',
  runId: 'run_1',
  title: 'Suspicious authentication activity',
  state: 'approval_pending',
  alertIds: ['alert:alt_1'],
  createdAt: '2026-06-30T02:00:01.000Z',
  updatedAt: '2026-06-30T02:05:00.000Z',
};

const alerts = [
  {
    id: 'alert:alt_1',
    title: 'Unusual login pattern',
    severity: 'high',
    assetId: 'asset:svc-api-gateway',
    detectorId: 'rule-unusual-login',
    confidence: 0.85,
  },
];

const investigation = {
  triageResults: [
    {
      id: 'wtri_1',
      escalation: 'investigate',
      escalationRationale: 'Escalate.',
      createdAt: '2026-06-30T02:01:00.000Z',
    },
  ],
  plans: [],
  evidenceAttachments: [
    {
      id: 'eatt_1',
      provenance: {
        sourceType: 'alert',
        sourceId: 'alert:alt_1',
        summary: 'Gateway auth burst exceeded baseline.',
        collectedByTool: 'list_alerts_for_asset',
      },
      isContradiction: false,
      confidence: 0.91,
    },
  ],
  candidateAssets: [
    {
      id: 'cand_1',
      assetId: 'asset:svc-api-gateway',
      confidence: 0.88,
      rationale: 'Top risk.',
    },
  ],
  hypotheses: [],
  hypothesisRevisions: [],
  proposals: [
    {
      id: 'prp_1',
      actionClass: 'class_2',
      targetAssetId: 'asset:svc-api-gateway',
      command: 'isolate',
      status: 'pending',
      rationale: 'Contain suspected abuse.',
      createdAt: '2026-06-30T02:09:00.000Z',
    },
  ],
  proposalRevisions: [],
  policyDecisions: [
    {
      id: 'pdc_1',
      proposalId: 'prp_1',
      outcome: 'approval_required',
      reasonCodes: ['approval_required_operational'],
      approvalRequirement: { required: true },
      explanationProse: 'Needs approval.',
      evaluatedAt: '2026-06-30T02:09:30.000Z',
    },
  ],
  approvals: [],
  executedActions: [],
};

describe('IncidentDetail', () => {
  beforeEach(() => {
    useIncident.mockReset();
    useIncidentRunAlerts.mockReset();
    useInvestigationDetail.mockReset();
    useIncidentRunAlerts.mockReturnValue({ data: alerts });
    useInvestigationDetail.mockReturnValue({
      isSuccess: true,
      data: investigation,
    });
  });
  afterEach(() => {
    cleanup();
  });

  it('renders a loading state while the incident loads', () => {
    useIncident.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
    });
    render(<IncidentDetail incidentId="incident:inc_1" />);
    expect(screen.getByTestId('incident-detail-loading')).toBeInTheDocument();
  });

  it('renders the incident-centric sections (timeline, proposals, agents, evidence)', () => {
    useIncident.mockReturnValue({
      isPending: false,
      isError: false,
      data: incident,
    });
    render(<IncidentDetail incidentId="incident:inc_1" />);

    expect(screen.getByTestId('incident-detail-summary')).toBeInTheDocument();
    expect(screen.getByTestId('incident-triage-timeline')).toBeInTheDocument();
    expect(screen.getByTestId('incident-proposals')).toBeInTheDocument();
    expect(screen.getByTestId('incident-agent-roster')).toBeInTheDocument();
    expect(screen.getByTestId('incident-alerts-evidence')).toBeInTheDocument();
    // Distinctly incident-centric: no live telemetry graph or live timeline.
    expect(screen.queryByTestId('operational-graph-view')).not.toBeInTheDocument();
    // Pending proposal surfaces as awaiting approval.
    expect(screen.getByTestId('proposal-prp_1')).toBeInTheDocument();
    // WATCHTOWER and BASTION are attributed as active from persisted artifacts.
    expect(screen.getByTestId('agent-role-WATCHTOWER')).toBeInTheDocument();
    expect(screen.getByTestId('agent-role-BASTION')).toBeInTheDocument();
    // SCRIBE after-action report link is present.
    expect(screen.getByText('Open after-action report')).toBeInTheDocument();
  });
});
