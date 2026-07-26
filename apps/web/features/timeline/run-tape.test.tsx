import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const timelineEntries = [
  {
    schemaVersion: 1,
    sequence: 4,
    eventId: 'evt_4',
    eventType: 'sim.alert.raised',
    label: 'Anomalous VPN session',
    timestamp: '2026-01-01T04:15:00.000Z',
    status: 'suspicious',
  },
  {
    schemaVersion: 1,
    sequence: 9,
    eventId: 'evt_9',
    eventType: 'sim.asset.compromised',
    label: 'Payments API compromised',
    timestamp: '2026-01-01T04:31:00.000Z',
    status: 'compromised',
  },
];

vi.mock('@/features/live-run/live-run-provider', () => ({
  useLiveRun: () => ({
    isLiveMode: true,
    state: { timelineEntries },
  }),
}));

import { RunTape } from './run-tape';

afterEach(() => {
  cleanup();
  useWorkspaceUiStore.getState().setTimelineCursorSequence(null);
});

describe('RunTape', () => {
  it('renders one beat per timeline entry and reads out the latest', () => {
    render(<RunTape />);

    expect(screen.getByTestId('run-tape-beat-4')).toBeInTheDocument();
    expect(screen.getByTestId('run-tape-beat-9')).toBeInTheDocument();
    expect(screen.getByTestId('run-tape-readout')).toHaveTextContent('Payments API compromised');
  });

  it('pins a beat on click and follows live again when unpinned', async () => {
    const user = userEvent.setup();
    render(<RunTape />);

    await user.click(screen.getByTestId('run-tape-beat-4'));
    expect(useWorkspaceUiStore.getState().workspace.timelineCursorSequence).toBe(4);
    expect(screen.getByTestId('run-tape-readout')).toHaveTextContent('Anomalous VPN session');

    await user.click(screen.getByTestId('run-tape-unpin'));
    expect(useWorkspaceUiStore.getState().workspace.timelineCursorSequence).toBeNull();
    expect(screen.getByTestId('run-tape-readout')).toHaveTextContent('Payments API compromised');
  });
});
