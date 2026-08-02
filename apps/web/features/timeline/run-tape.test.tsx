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

import { RunTape, interpretTapeDrag, TAPE_DRAG_THRESHOLD_PX } from './run-tape';

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

describe('RunTape as the Chronicle handle', () => {
  it('shows no chronicle affordances unless it is handed the handle role', () => {
    render(<RunTape />);
    expect(screen.queryByTestId('chronicle-toggle')).not.toBeInTheDocument();
    expect(screen.queryByTestId('chronicle-grab')).not.toBeInTheDocument();
  });

  it('offers a labelled chevron that toggles the chronicle without touching tick semantics', async () => {
    const user = userEvent.setup();
    const setOpen = vi.fn();
    render(<RunTape chronicle={{ open: false, setOpen }} />);

    const toggle = screen.getByTestId('chronicle-toggle');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveAccessibleName('Open chronicle');

    await user.click(toggle);
    expect(setOpen).toHaveBeenCalledWith(true);

    // Tick clicks still pin; the handle is a separate hit target.
    await user.click(screen.getByTestId('run-tape-beat-4'));
    expect(useWorkspaceUiStore.getState().workspace.timelineCursorSequence).toBe(4);
  });

  it('announces the close affordance while open', () => {
    render(<RunTape chronicle={{ open: true, setOpen: vi.fn() }} />);
    const toggle = screen.getByTestId('chronicle-toggle');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAccessibleName('Close chronicle');
    expect(screen.getByTestId('chronicle-grab')).toBeInTheDocument();
  });

  it('interprets grab drags: up past the threshold opens, down closes, less is noise', () => {
    expect(interpretTapeDrag(-TAPE_DRAG_THRESHOLD_PX)).toBe('open');
    expect(interpretTapeDrag(TAPE_DRAG_THRESHOLD_PX)).toBe('close');
    expect(interpretTapeDrag(-(TAPE_DRAG_THRESHOLD_PX - 1))).toBeNull();
    expect(interpretTapeDrag(TAPE_DRAG_THRESHOLD_PX - 1)).toBeNull();
    expect(interpretTapeDrag(0)).toBeNull();
  });
});
