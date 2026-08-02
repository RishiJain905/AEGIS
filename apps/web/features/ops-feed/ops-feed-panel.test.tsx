import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { RunFeedEntry } from '@/features/command-surface';

import { OpsFeedPanel } from './ops-feed-panel';

const useRunFeed = vi.fn();
vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return { ...actual, useRunFeed: (runId: string) => useRunFeed(runId) as unknown };
});

// The panel resolves asset display names off the run graph (the same cached query the
// workspace already holds) and hands the operator to the node on click.
const graphSnapshot = {
  data: {
    snapshot: {
      nodes: [{ id: 'asset:svc-identity-broker', label: 'Identity Broker' }],
    },
  },
};
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRunGraph: () => graphSnapshot,
}));

const focusAsset = vi.fn();
vi.mock('@/features/operational-graph', () => ({
  useFocusAsset: () => focusAsset,
}));

function feedResult(entries: RunFeedEntry[]) {
  return { data: entries, isPending: false, isError: false, refetch: vi.fn() };
}

function entry(overrides: Partial<RunFeedEntry> & { sequence: number }): RunFeedEntry {
  return {
    schemaVersion: 1,
    eventId: `evt-${String(overrides.sequence)}`,
    type: 'agent.task.completed',
    category: 'agent',
    simTime: '2026-07-22T00:01:02.000Z',
    initiator: null,
    summary: 'WATCHTOWER swept alerts',
    payload: {},
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('OpsFeedPanel', () => {
  it('renders feed entries with a detection beat and a collapse summary', () => {
    useRunFeed.mockReturnValue(
      feedResult([
        entry({ sequence: 1, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
        entry({ sequence: 2, initiator: 'autonomy', payload: { outcome: 'no_change' } }),
        entry({
          sequence: 3,
          category: 'reveal',
          type: 'sim.hidden_condition.revealed',
          summary: 'Exfil path exposed',
        }),
      ]),
    );
    render(<OpsFeedPanel runId="run_x" />);
    expect(screen.getByTestId('ops-feed-detection')).toBeInTheDocument();
    expect(screen.getByTestId('ops-feed-collapsed')).toHaveTextContent('2 routine autonomy checks');
  });

  it('shows an empty state when the feed is quiet', () => {
    useRunFeed.mockReturnValue(feedResult([]));
    render(<OpsFeedPanel runId="run_x" />);
    expect(screen.getByText(/Quiet on the floor/i)).toBeInTheDocument();
  });

  it('renders one order as one card, folding its whole event trail into the disclosure', () => {
    useRunFeed.mockReturnValue(
      feedResult([
        entry({
          sequence: 5,
          type: 'operator.action.proposed',
          category: 'operator_action',
          summary: 'operator.action.proposed (asset:svc-identity-broker)',
          initiator: 'operator',
          payload: {
            proposalId: 'prop_1',
            incidentId: 'incident:inc_1',
            scenarioCommand: 'isolate',
            actionClass: 'class_2',
            targetAssetId: 'asset:svc-identity-broker',
            justification: 'Broker is beaconing; cutting it off.',
          },
        }),
        entry({
          sequence: 6,
          type: 'action.executed',
          category: 'execution',
          summary: 'action.executed',
          payload: {
            proposalId: 'prop_1',
            incidentId: 'incident:inc_1',
            approvalId: 'apr_1',
            executedActionId: 'act_1',
            commandId: 'cmd_1',
          },
        }),
      ]),
    );
    render(<OpsFeedPanel runId="run_x" />);

    const cards = screen.getAllByTestId('ops-feed-action');
    expect(cards).toHaveLength(1);
    expect(cards[0]).toHaveAttribute('data-stage', 'executed');
    expect(cards[0]).toHaveTextContent('Isolate');
    expect(cards[0]).toHaveTextContent('Class 2 · Operational');
    expect(cards[0]).toHaveTextContent('Severs the asset from the network');
    // The reason the operator gave rides on the proposed event; the surviving card is the
    // executed one, so this only reads if the fold carried it across.
    expect(cards[0]).toHaveTextContent('Broker is beaconing; cutting it off.');
    expect(screen.getAllByText('Identity Broker')[0]).toBeInTheDocument();
    const disclosure = screen.getByText('Raw events (2)');
    expect(disclosure).toBeInTheDocument();
    expect(cards[0]).toHaveTextContent('operator.action.proposed');
    expect(cards[0]).toHaveTextContent('action.executed');
  });

  it('hands the operator to the target node when an action target is clicked', () => {
    useRunFeed.mockReturnValue(
      feedResult([
        entry({
          sequence: 5,
          type: 'operator.action.proposed',
          category: 'operator_action',
          payload: {
            proposalId: 'prop_1',
            scenarioCommand: 'isolate',
            actionClass: 'class_2',
            targetAssetId: 'asset:svc-identity-broker',
          },
        }),
      ]),
    );
    render(<OpsFeedPanel runId="run_x" />);

    fireEvent.click(screen.getByText('Identity Broker'));
    expect(focusAsset).toHaveBeenCalledWith('asset:svc-identity-broker');
  });

  it('has no accessibility violations in dark and light themes', async () => {
    useRunFeed.mockReturnValue(
      feedResult([
        entry({
          sequence: 1,
          category: 'alert',
          summary: 'Suspicious auth burst',
          initiator: null,
        }),
        entry({ sequence: 2, initiator: 'operator', summary: 'TRACE followed the lead' }),
      ]),
    );
    for (const theme of ['dark', 'light'] as const) {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        const { container } = render(<OpsFeedPanel runId="run_x" />);
        const results = await axe(container);
        expect(results.violations).toHaveLength(0);
        cleanup();
      } finally {
        document.documentElement.removeAttribute('data-theme');
      }
    }
  });
});
