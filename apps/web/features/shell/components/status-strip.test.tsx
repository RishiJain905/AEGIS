import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ConnectionHealthState } from '@aegis/contracts-ts';

const {
  useConnectionStatus,
  useRun,
  useRunReadOnly,
  useRunGraph,
  useLiveRun,
  useAfterActionReport,
} = vi.hoisted(() => ({
  useConnectionStatus: vi.fn(),
  useRun: vi.fn(),
  useRunReadOnly: vi.fn(),
  useRunGraph: vi.fn(),
  useLiveRun: vi.fn(),
  useAfterActionReport: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useConnectionStatus,
  useRun,
  useRunReadOnly,
  useRunGraph,
}));
vi.mock('@/features/live-run', () => ({
  useLiveRun,
  ThreatTempoIndicator: () => null,
}));
vi.mock('@/features/reports/use-report-queries', () => ({
  useAfterActionReport,
}));
vi.mock('@/features/command-surface', () => ({ readRunLoadout: () => null }));
vi.mock('@/features/comms-desk', () => ({ SitrepButton: () => null }));
vi.mock('@/features/loadout', () => ({
  LoadoutChips: () => null,
  RoeDial: () => null,
}));
vi.mock('@/features/auth', () => ({ OperatorIdentityBadge: () => null }));

import { StatusStrip } from './status-strip';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function setup({
  connectionStatus = 'connected',
  liveRun = null,
  runStatus = 'running',
}: {
  connectionStatus?: string;
  liveRun?: unknown;
  runStatus?: string;
} = {}) {
  useConnectionStatus.mockReturnValue({ data: connectionStatus });
  useRun.mockReturnValue({ data: { status: runStatus } });
  useRunReadOnly.mockReturnValue({ data: false });
  useRunGraph.mockReturnValue({ data: undefined });
  useAfterActionReport.mockReturnValue({ data: undefined });
  useLiveRun.mockReturnValue(liveRun);
  render(<StatusStrip runId={RUN_ID} />);
}

describe('StatusStrip connection surface', () => {
  it('keeps the fixed-size connection badge as the at-a-glance indicator', () => {
    setup({ connectionStatus: 'offline' });
    expect(screen.getByTestId('connection-status-badge')).toHaveTextContent('Offline');
  });

  it('raises no banner of its own when the fixture connection is offline', () => {
    setup({ connectionStatus: 'offline' });
    expect(screen.queryAllByRole('alert')).toHaveLength(0);
    expect(screen.queryByText(/Realtime updates are unavailable/)).toBeNull();
  });

  it('raises no banner of its own when a live run reports stale state', () => {
    setup({
      liveRun: {
        isLiveMode: true,
        bootstrapSnapshot: null,
        graphRevision: 0,
        state: {
          connectionHealth: ConnectionHealthState.STALE,
          isStale: true,
          lastAppliedSequence: 7,
          runStatus: 'running',
          simTime: null,
        },
      },
    });
    expect(screen.getByTestId('connection-status-badge')).toHaveTextContent('Stale');
    expect(screen.queryAllByRole('alert')).toHaveLength(0);
    expect(screen.queryByText(/State may be stale/)).toBeNull();
  });
});

describe('StatusStrip instrument rail (BUG-011)', () => {
  it('shows a healthy link and a paused sim as two separate facts', () => {
    setup({
      liveRun: {
        isLiveMode: true,
        bootstrapSnapshot: null,
        graphRevision: 0,
        state: {
          connectionHealth: ConnectionHealthState.SIMULATOR_PAUSED,
          isStale: false,
          lastAppliedSequence: 12,
          runStatus: 'paused',
          simTime: '2026-01-01T00:05:00Z',
        },
      },
    });
    expect(screen.getByTestId('connection-status-badge')).toHaveTextContent('Connected');
    expect(screen.getByTestId('run-status')).toHaveTextContent('Paused');
  });

  it('derives threat posture from the disclosed graph outside live mode', () => {
    useConnectionStatus.mockReturnValue({ data: 'connected' });
    useRun.mockReturnValue({ data: { status: 'running' } });
    useRunReadOnly.mockReturnValue({ data: false });
    useAfterActionReport.mockReturnValue({ data: undefined });
    useLiveRun.mockReturnValue(null);
    useRunGraph.mockReturnValue({
      data: { snapshot: { nodes: [{ status: 'normal' }, { status: 'compromised' }] } },
    });
    render(<StatusStrip runId={RUN_ID} />);
    expect(screen.getByTestId('threat-posture')).toHaveTextContent('Critical');
  });

  it('lights the report instrument once a terminal run has a report', () => {
    useConnectionStatus.mockReturnValue({ data: 'connected' });
    useRun.mockReturnValue({ data: { status: 'completed' } });
    useRunReadOnly.mockReturnValue({ data: true });
    useRunGraph.mockReturnValue({ data: undefined });
    useAfterActionReport.mockReturnValue({ data: { versionNumber: 1 } });
    useLiveRun.mockReturnValue(null);
    render(<StatusStrip runId={RUN_ID} />);
    expect(screen.getByTestId('run-status')).toHaveTextContent('Complete');
    expect(screen.getByTestId('run-outcome')).toHaveTextContent('Report ready');
  });
});
