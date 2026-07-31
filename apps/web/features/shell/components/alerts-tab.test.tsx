import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useLiveRun, useRunActivity, useRunAlerts, useRunIncidents, useRunGraph } = vi.hoisted(
  () => ({
    useLiveRun: vi.fn(),
    useRunActivity: vi.fn(),
    useRunAlerts: vi.fn(),
    useRunIncidents: vi.fn(),
    useRunGraph: vi.fn(),
  }),
);

vi.mock('@/features/alerts', () => ({
  AlertsPanel: ({ alerts }: { alerts: unknown[] }) => (
    <div data-testid="alerts-panel-stub" data-count={alerts.length} />
  ),
}));
vi.mock('@/features/live-run', () => ({
  useLiveRun,
  useRunActivity,
  ACTIVITY_COPY: {
    quiet: { label: 'Quiet', detail: 'Nothing is moving on the floor.' },
    elevated: { label: 'Elevated', detail: 'The run is producing signal.' },
    active: { label: 'Active', detail: 'Something is happening right now.' },
  },
}));
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRunAlerts,
  useRunIncidents,
  useRunGraph,
}));

import { AlertsTab } from './alerts-tab';

function settled(data: unknown) {
  return { isPending: false, isError: false, data, refetch: vi.fn() };
}

beforeEach(() => {
  vi.clearAllMocks();
  useLiveRun.mockReturnValue(null);
  useRunActivity.mockReturnValue({ level: 'quiet', count: 0, windowSeconds: 90, buckets: [] });
  useRunAlerts.mockReturnValue(settled([]));
  useRunIncidents.mockReturnValue(settled([]));
  useRunGraph.mockReturnValue(settled({ snapshot: null }));
});

afterEach(() => {
  cleanup();
});

describe('AlertsTab', () => {
  it('renders the alerts rail with run-scoped data', () => {
    useRunAlerts.mockReturnValue(settled([{ id: 'a1' }]));
    render(<AlertsTab runId="run_1" />);
    expect(screen.getByTestId('alerts-panel-stub')).toHaveAttribute('data-count', '1');
    expect(screen.queryByTestId('alerts-quiet-floor')).not.toBeInTheDocument();
  });

  it('speaks for the empty rail with the live activity reading', () => {
    render(<AlertsTab runId="run_1" />);
    const quiet = screen.getByTestId('alerts-quiet-floor');
    expect(quiet).toHaveTextContent('No alerts yet');
    expect(quiet).toHaveTextContent('Nothing is moving on the floor.');
  });

  it('stays silent about a quiet floor when a reveal is already on the tape', () => {
    useLiveRun.mockReturnValue({
      isLiveMode: true,
      state: {
        timelineEntries: [
          {
            eventType: 'sim.hidden_condition.revealed',
            label: 'Cause revealed',
            sequence: 9,
            timestamp: '2026-01-01T00:03:00Z',
          },
        ],
      },
    });
    render(<AlertsTab runId="run_1" />);
    expect(screen.queryByTestId('alerts-quiet-floor')).not.toBeInTheDocument();
  });
});
