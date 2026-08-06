import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

vi.mock('next/navigation', () => ({
  usePathname: () => '/runs/run_a',
}));

vi.mock('@/features/agent-chat/use-agent-chat', () => ({
  useRunAgentSessions: () => ({ data: [] }),
}));

const getRun = vi.fn();
const listAlerts = vi.fn();
const listIncidents = vi.fn();
const getInvestigationDetail = vi.fn();
const getAfterActionReport = vi.fn();
vi.mock('@/lib/api/api-client-provider', () => ({
  useApiClient: () => ({
    getRun,
    listAlerts,
    listIncidents,
    getInvestigationDetail,
    getAfterActionReport,
  }),
}));

import type { TutorialEvidenceKey } from './tutorial-contract';
import { useTutorialEvidence } from './use-tutorial-evidence';

const RUN = {
  id: 'run_a',
  scenarioVersionId: 'scenario-version:1.0.0-synthetic-training',
  status: 'running',
  simTime: '2026-01-01T00:10:00.000Z',
};

const CORRELATED_INCIDENT = 'incident:inc_1';
const OPERATOR_INCIDENT = 'incident:inc_op_run_a';

function incident(id: string) {
  return { id, runId: 'run_a' };
}

function detail(incidentId: string, executedActions: unknown[] = [], proposals: unknown[] = []) {
  return {
    schemaVersion: 1,
    incidentId,
    runId: 'run_a',
    triageResults: [],
    plans: [],
    evidenceAttachments: [],
    notes: [],
    candidateAssets: [],
    overlays: [],
    hypotheses: [],
    hypothesisRevisions: [],
    hypothesisComparisons: [],
    verificationRequests: [],
    proposals,
    proposalRevisions: [],
    policyDecisions: [],
    approvals: [],
    executedActions,
  };
}

function executedAction(proposalId: string) {
  return {
    schemaVersion: 1,
    id: `act_${proposalId}`,
    proposalId,
    runId: 'run_a',
    resultEventId: 'evt_1',
    idempotencyKey: 'k',
    executedAt: '2026-01-01T00:05:00.000Z',
  };
}

function proposal(id: string, command: string) {
  return {
    schemaVersion: 2,
    id,
    incidentId: OPERATOR_INCIDENT,
    agentSessionId: 'agent-session:operator-console',
    actionClass: command === 'observe' ? 'class_0' : 'class_2',
    targetAssetId: 'asset:device-workstation-alpha',
    command,
    scenarioCommand: command,
    currentRevisionId: `prv_${id}`,
    status: 'executed',
    rationale: 'Operator-directed action.',
    revision: 1,
    createdAt: '2026-01-01T00:05:00.000Z',
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function renderEvidence(pendingKeys: TutorialEvidenceKey[]) {
  return renderHook(
    () =>
      useTutorialEvidence('run_a', {
        enabled: true,
        pendingKeys,
        watchRunClock: false,
      }),
    { wrapper },
  );
}

beforeEach(() => {
  getRun.mockReset();
  listAlerts.mockReset();
  listIncidents.mockReset();
  getInvestigationDetail.mockReset();
  getAfterActionReport.mockReset();
  getRun.mockResolvedValue(RUN);
  listAlerts.mockResolvedValue([]);
  listIncidents.mockResolvedValue([]);
  getAfterActionReport.mockResolvedValue(null);
  useWorkspaceUiStore.getState().setSelectedIncidentId(null);
  useWorkspaceUiStore.getState().setSelectedEntityId(null);
});

afterEach(() => {
  cleanup();
});

describe('useTutorialEvidence · executed-action evidence', () => {
  it('reads executed actions across every incident, not just the one the operator has open', async () => {
    // The QA repro (2026-08-06, P1): the operator runs Observe on the tutorial's
    // command-observe beat, but the executed action anchors to the deterministic operator
    // incident while the operator has the correlated incident open — so the objective could
    // never advance. The evidence must see the operator incident's detail too.
    listIncidents.mockResolvedValue([incident(CORRELATED_INCIDENT), incident(OPERATOR_INCIDENT)]);
    getInvestigationDetail.mockImplementation((incidentId: string) => {
      if (incidentId === OPERATOR_INCIDENT) {
        return Promise.resolve(
          detail(
            OPERATOR_INCIDENT,
            [executedAction('prp_observe')],
            [proposal('prp_observe', 'observe')],
          ),
        );
      }
      return Promise.resolve(detail(incidentId));
    });
    act(() => {
      useWorkspaceUiStore.getState().setSelectedIncidentId(CORRELATED_INCIDENT);
    });

    const { result } = renderEvidence(['operatorActionExecuted']);

    await waitFor(() => {
      expect(result.current.evidence.operatorActionExecuted).toBe(true);
    });
  });

  it('stays false while no incident on the run has an executed action', async () => {
    listIncidents.mockResolvedValue([incident(CORRELATED_INCIDENT)]);
    getInvestigationDetail.mockResolvedValue(detail(CORRELATED_INCIDENT));

    const { result } = renderEvidence(['operatorActionExecuted']);

    await waitFor(() => {
      expect(getInvestigationDetail).toHaveBeenCalled();
    });
    expect(result.current.evidence.operatorActionExecuted).toBe(false);
  });

  it('counts a Class 2+ executed action as containment, wherever it was anchored', async () => {
    listIncidents.mockResolvedValue([incident(CORRELATED_INCIDENT), incident(OPERATOR_INCIDENT)]);
    getInvestigationDetail.mockImplementation((incidentId: string) => {
      if (incidentId === OPERATOR_INCIDENT) {
        return Promise.resolve(
          detail(
            OPERATOR_INCIDENT,
            [executedAction('prp_isolate')],
            [proposal('prp_isolate', 'isolate')],
          ),
        );
      }
      return Promise.resolve(detail(incidentId));
    });

    const { result } = renderEvidence(['containmentActionExecuted']);

    await waitFor(() => {
      expect(result.current.evidence.containmentActionExecuted).toBe(true);
    });
  });

  it('does not count a Class 0 observe as containment', async () => {
    listIncidents.mockResolvedValue([incident(OPERATOR_INCIDENT)]);
    getInvestigationDetail.mockResolvedValue(
      detail(
        OPERATOR_INCIDENT,
        [executedAction('prp_observe')],
        [proposal('prp_observe', 'observe')],
      ),
    );

    const { result } = renderEvidence(['containmentActionExecuted']);

    await waitFor(() => {
      expect(getInvestigationDetail).toHaveBeenCalled();
    });
    expect(result.current.evidence.containmentActionExecuted).toBe(false);
  });
});
