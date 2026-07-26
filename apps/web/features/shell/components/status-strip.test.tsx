import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ConnectionHealthState } from '@aegis/contracts-ts';

const { useConnectionStatus, useRun, useRunReadOnly, useLiveRun } = vi.hoisted(() => ({
  useConnectionStatus: vi.fn(),
  useRun: vi.fn(),
  useRunReadOnly: vi.fn(),
  useLiveRun: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useConnectionStatus,
  useRun,
  useRunReadOnly,
}));
vi.mock('@/features/live-run', () => ({
  useLiveRun,
  ThreatTempoIndicator: () => null,
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
}: {
  connectionStatus?: string;
  liveRun?: unknown;
} = {}) {
  useConnectionStatus.mockReturnValue({ data: connectionStatus });
  useRun.mockReturnValue({ data: { status: 'running' } });
  useRunReadOnly.mockReturnValue({ data: false });
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
