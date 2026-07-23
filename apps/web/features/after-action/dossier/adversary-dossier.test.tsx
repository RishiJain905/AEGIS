import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { DossierEvent } from './assemble-dossier';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const CREDENTIALS_ASSET = 'asset:identity-svc-logistics-bot';
const CONDITION = 'hidden-cause-compromised-credentials';
const T0 = Date.parse('2026-01-01T00:00:00.000Z');
const at = (m: number): string => new Date(T0 + m * 60_000).toISOString();

/* --- mocks ------------------------------------------------------------- */

const useRun = vi.fn();
const useRunGraph = vi.fn();
const useAfterActionView = vi.fn();
const fetchAllRunEvents = vi.fn();

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRun: (runId: string) => useRun(runId) as unknown,
  useRunGraph: (runId: string, options?: { enabled?: boolean }) =>
    useRunGraph(runId, options) as unknown,
}));

vi.mock('@/features/after-action/use-after-action-queries', () => ({
  useAfterActionView: (runId: string) => useAfterActionView(runId) as unknown,
}));

vi.mock('./fetch-run-events', () => ({
  fetchAllRunEvents: (runId: string, signal?: AbortSignal) =>
    fetchAllRunEvents(runId, signal) as Promise<DossierEvent[]>,
}));

// Imported after the mocks are registered.
import { AdversaryDossier } from './adversary-dossier';

function ev(sequence: number, type: string, minutes: number, payload: Record<string, unknown>): DossierEvent {
  return {
    sequence,
    type,
    simTime: at(minutes),
    actorType: type.startsWith('operator') || type === 'action.executed' ? 'operator' : 'system',
    actorId: 'asset:sim',
    subjectType: 'asset',
    subjectId: 'asset:sim',
    payload,
  };
}

function terminalEvents(): DossierEvent[] {
  return [
    ev(1, 'sim.run.started', 0, {}),
    ev(2, 'sim.branch.selected', 0, { branchGroup: 'root-cause', branchId: 'branch-cause-credentials' }),
    ev(3, 'sim.hidden_condition.triggered', 5, { conditionId: CONDITION }),
    ev(4, 'sim.asset.status_changed', 15, { assetId: CREDENTIALS_ASSET, status: 'compromised' }),
    ev(5, 'alert.created', 21, { assetId: CREDENTIALS_ASSET, title: 'Anomalous authentication' }),
    ev(6, 'sim.hidden_condition.revealed', 25, { conditionId: CONDITION }),
    ev(7, 'action.executed', 31, { proposalId: 'prp_1' }),
    ev(8, 'sim.run.stopped', 40, {}),
  ];
}

function scoreStub() {
  return {
    schemaVersion: 1,
    scoreId: 's1',
    runId: RUN_ID,
    overallScore: 82,
    maxScore: 100,
    grade: 'B',
    passed: true,
    components: [
      { criterionId: 'c1', label: 'Detection', weight: 1, rawScore: 0.8, weightedContribution: 80, explanations: [] },
    ],
    provenance: {
      scenarioVersion: 'v1',
      rubricVersion: 'v1',
      gradingEngineVersion: 'v1',
      inputEventSequenceFrom: 1,
      inputEventSequenceTo: 40,
      integrityChecksum: 'a',
      fingerprint: 'b',
      inputChecksum: 'c',
      calculatedAt: at(41),
    },
    decisionReviews: [],
    missedEvidence: [],
    validAlternatives: [],
    coachingAuthoritative: false,
    hiddenCauseId: CONDITION,
    hiddenCauseLabel: 'Compromised service account credentials',
    hiddenCauseRevealed: true,
  };
}

function renderDossier() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdversaryDossier runId={RUN_ID} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useRun.mockReset();
  useRunGraph.mockReset();
  useAfterActionView.mockReset();
  fetchAllRunEvents.mockReset();
  useRunGraph.mockReturnValue({ data: null });
  useAfterActionView.mockReturnValue({ data: undefined });
});

afterEach(() => {
  cleanup();
});

describe('AdversaryDossier — fog-of-war gating', () => {
  it.each(['created', 'running', 'paused'])(
    'seals the dossier and never fetches ground truth while the run is %s',
    async (status) => {
      useRun.mockReturnValue({ data: { status }, isLoading: false, isError: false });
      renderDossier();

      expect(screen.getByTestId('dossier-sealed')).toBeInTheDocument();
      // No attacker campaign content leaks mid-run.
      expect(screen.queryByTestId('adversary-dossier')).not.toBeInTheDocument();
      expect(screen.queryByTestId('dossier-timeline')).not.toBeInTheDocument();
      expect(screen.queryByText(/Compromised service account credentials/)).not.toBeInTheDocument();
      // The event stream is never even requested for a live run.
      await Promise.resolve();
      expect(fetchAllRunEvents).not.toHaveBeenCalled();
    },
  );
});

describe('AdversaryDossier — terminal run', () => {
  beforeEach(() => {
    useRun.mockReturnValue({
      data: { status: 'stopped', startedAt: at(0), simTime: at(40) },
      isLoading: false,
      isError: false,
    });
    useAfterActionView.mockReturnValue({ data: { score: scoreStub() } });
    useRunGraph.mockReturnValue({
      data: { snapshot: { nodes: [{ id: CREDENTIALS_ASSET, label: 'Logistics Service Bot' }] } },
    });
    fetchAllRunEvents.mockResolvedValue(terminalEvents());
  });

  it('reconstructs the campaign with root cause, lanes and detection crossings', async () => {
    renderDossier();

    await waitFor(() => {
      expect(screen.getByTestId('adversary-dossier')).toBeInTheDocument();
    });
    expect(fetchAllRunEvents).toHaveBeenCalledWith(RUN_ID, expect.anything());
    expect(screen.getByTestId('dossier-root-cause')).toHaveTextContent(
      'Compromised service account credentials',
    );
    expect(screen.getByTestId('dossier-timeline')).toBeInTheDocument();
    expect(screen.getAllByTestId('dossier-attacker-row').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('dossier-defender-row').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('dossier-crossing').length).toBe(2);
    expect(screen.getByTestId('dossier-exfil-outcome')).toHaveTextContent('Contained');
  });

  it('has no detectable accessibility violations', async () => {
    renderDossier();
    await waitFor(() => {
      expect(screen.getByTestId('adversary-dossier')).toBeInTheDocument();
    });
    const results = await axe(document.body);
    expect(results.violations).toHaveLength(0);
  });
});
