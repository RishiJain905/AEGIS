import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { RunFeedEntry } from '@/features/command-surface';

import { OpsFeedPanel } from './ops-feed-panel';

const useRunFeed = vi.fn();
vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return { ...actual, useRunFeed: (runId: string) => useRunFeed(runId) as unknown };
});

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
