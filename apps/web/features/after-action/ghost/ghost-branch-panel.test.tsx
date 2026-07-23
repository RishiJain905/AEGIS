import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type {
  GhostBranchResultV1,
  GhostDecisionPointV1,
  GhostDecisionPointsV1,
} from '@aegis/contracts-ts';

import { ApiClientError } from '@/lib/api/types';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const TARGET_ASSET = 'asset:identity-svc-logistics-bot';
const DECISION_REF = 'action:7';
const T0 = Date.parse('2026-01-01T00:00:00.000Z');
const at = (m: number): string => new Date(T0 + m * 60_000).toISOString();

/* --- mocks ------------------------------------------------------------- */

const useRun = vi.fn();
const useGhostDecisionPoints = vi.fn();
const useGhostRunMutation = vi.fn();

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRun: (runId: string) => useRun(runId) as unknown,
  // use-dossier imports this too; it is never called by the ghost panel.
  useRunGraph: () => ({ data: null }),
}));

vi.mock('@/features/after-action/use-after-action-queries', () => ({
  useAfterActionView: () => ({ data: undefined }),
}));

vi.mock('./use-ghost-branch', () => ({
  useGhostDecisionPoints: (runId: string, terminal: boolean) =>
    useGhostDecisionPoints(runId, terminal) as unknown,
  useGhostRunMutation: (runId: string) => useGhostRunMutation(runId) as unknown,
}));

// Imported after the mocks are registered.
import { GhostBranchPanel } from './ghost-branch-panel';

/* --- builders ---------------------------------------------------------- */

function executedDecision(): GhostDecisionPointV1 {
  return {
    schemaVersion: 1,
    decisionRef: DECISION_REF,
    kind: 'executed_action',
    sequence: 7,
    simTime: at(10),
    scenarioCommand: 'isolate',
    targetAssetId: TARGET_ASSET,
    actionClass: 'Class 2',
    label: 'Isolate Logistics Service Bot',
  };
}

function decisionPointsStub(points: GhostDecisionPointV1[]): GhostDecisionPointsV1 {
  return { schemaVersion: 1, runId: RUN_ID, decisionPoints: points };
}

function resultStub(): GhostBranchResultV1 {
  return {
    schemaVersion: 1,
    runId: RUN_ID,
    decisionRef: DECISION_REF,
    mode: 'substitute',
    requestFingerprint: 'fp_0123456789abcdef',
    resultHash: 'rh_0123456789abcdef',
    divergenceSequence: 12,
    divergenceSimTime: at(20),
    stepsSimulated: 8,
    realOutcome: {
      label: 'Breached',
      finalStatuses: [{ assetId: TARGET_ASSET, status: 'compromised' }],
      compromisedCount: 2,
      containedCount: 0,
      breachOccurred: true,
      breachAssetIds: [TARGET_ASSET],
    },
    ghostOutcome: {
      label: 'Held',
      finalStatuses: [{ assetId: TARGET_ASSET, status: 'contained' }],
      compromisedCount: 0,
      containedCount: 1,
      breachOccurred: false,
      breachAssetIds: [],
    },
    assetDiffs: [{ assetId: TARGET_ASSET, realStatus: 'compromised', ghostStatus: 'contained' }],
    ghostTimeline: [
      {
        sequence: 13,
        simTime: at(22),
        kind: 'asset_effect',
        label: 'Isolation held the bot',
        assetId: TARGET_ASSET,
        status: 'contained',
      },
    ],
    realOverallScore: 62,
    verdict: 'Restricting access would have contained the breach.',
  };
}

function idleMutation(overrides: Record<string, unknown> = {}) {
  return { mutate: vi.fn(), isPending: false, error: null, data: undefined, ...overrides };
}

function decisionsQuery(overrides: Record<string, unknown> = {}) {
  return { data: undefined, isLoading: false, isError: false, error: null, ...overrides };
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GhostBranchPanel runId={RUN_ID} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useRun.mockReset();
  useGhostDecisionPoints.mockReset();
  useGhostRunMutation.mockReset();
  useGhostRunMutation.mockReturnValue(idleMutation());
  useGhostDecisionPoints.mockReturnValue(decisionsQuery());
});

afterEach(() => {
  cleanup();
});

describe('GhostBranchPanel — fog-of-war gating', () => {
  it.each(['created', 'running', 'paused'])(
    'seals the panel and never requests decision points while the run is %s',
    (status) => {
      useRun.mockReturnValue({ data: { status }, isLoading: false, isError: false });
      renderPanel();

      expect(screen.getByTestId('ghost-branch-sealed')).toBeInTheDocument();
      expect(screen.queryByTestId('ghost-branch-panel')).not.toBeInTheDocument();
      // The decision-points hook only mounts inside the terminal workbench.
      expect(useGhostDecisionPoints).not.toHaveBeenCalled();
    },
  );
});

describe('GhostBranchPanel — terminal run', () => {
  beforeEach(() => {
    useRun.mockReturnValue({
      data: { status: 'stopped', startedAt: at(0), simTime: at(40) },
      isLoading: false,
      isError: false,
    });
    useGhostDecisionPoints.mockReturnValue(
      decisionsQuery({ data: decisionPointsStub([executedDecision()]) }),
    );
  });

  it('renders the fetched decision points in the picker', () => {
    renderPanel();

    expect(screen.getByTestId('ghost-branch-panel')).toBeInTheDocument();
    expect(screen.getByTestId(`ghost-decision-${DECISION_REF}`)).toBeInTheDocument();
    expect(screen.getByTestId('ghost-decision-list')).toHaveTextContent(
      'Isolate Logistics Service Bot',
    );
  });

  it('runs a substitute branch with a correctly-shaped GhostBranchRequestV1', () => {
    const mutate = vi.fn();
    useGhostRunMutation.mockReturnValue(idleMutation({ mutate }));
    renderPanel();

    fireEvent.click(screen.getByTestId(`ghost-decision-${DECISION_REF}`));
    fireEvent.change(screen.getByLabelText('Alternate command'), {
      target: { value: 'restrict_access' },
    });
    fireEvent.click(screen.getByTestId('ghost-run'));

    expect(mutate).toHaveBeenCalledWith({
      schemaVersion: 1,
      decisionRef: DECISION_REF,
      mode: 'substitute',
      alternateCommand: 'restrict_access',
      alternateTargetAssetId: TARGET_ASSET,
    });
  });

  it('renders the real-vs-ghost outcome, an asset diff and a divergence beat on success', () => {
    useGhostRunMutation.mockReturnValue(idleMutation({ data: resultStub() }));
    renderPanel();

    expect(screen.getByTestId('ghost-results')).toBeInTheDocument();
    expect(screen.getByTestId('ghost-verdict')).toHaveTextContent(
      'Restricting access would have contained the breach.',
    );
    expect(screen.getByTestId('ghost-real')).toBeInTheDocument();
    expect(screen.getByTestId('ghost-ghost')).toBeInTheDocument();
    expect(screen.getByTestId(`ghost-diff-${TARGET_ASSET}`)).toBeInTheDocument();
    expect(screen.getAllByTestId('ghost-timeline-beat').length).toBeGreaterThan(0);
  });

  it('surfaces the special RUN_NOT_TERMINAL message on that error code', () => {
    useGhostRunMutation.mockReturnValue(
      idleMutation({
        error: new ApiClientError({
          code: 'RUN_NOT_TERMINAL',
          message: 'not terminal',
          status: 409,
        }),
      }),
    );
    renderPanel();

    expect(screen.getByTestId('ghost-error')).toHaveTextContent(/available only after it ends/i);
  });

  it('has no detectable accessibility violations on the results state', async () => {
    useGhostRunMutation.mockReturnValue(idleMutation({ data: resultStub() }));
    renderPanel();

    const results = await axe(document.body);
    expect(results.violations).toHaveLength(0);
  });
});
