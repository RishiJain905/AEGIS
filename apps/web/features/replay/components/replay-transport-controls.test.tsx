import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { ReplayTransportControls } from '@/features/replay/components/replay-transport-controls';
import { useReplayStore } from '@/stores/replay-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function seed(sequence: number, maxSequence: number) {
  useReplayStore.getState().enterHistorical(RUN_ID, { sequence, maxSequence });
  useReplayStore.getState().setLoadStatus('ready');
}

describe('ReplayTransportControls', () => {
  beforeEach(() => {
    useReplayStore.getState().clear();
  });

  afterEach(() => {
    cleanup();
    useReplayStore.getState().clear();
  });

  it('renders nothing before a cursor exists', () => {
    const { container } = render(<ReplayTransportControls />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the current cursor and total range', () => {
    seed(120, 500);
    render(<ReplayTransportControls />);
    const readout = screen.getByTestId('replay-position-readout');
    expect(readout.textContent).toContain('120');
    expect(readout.textContent).toContain('of 500');
    expect(readout.textContent).toContain('range 0–500');
    expect(screen.getByTestId('replay-load-status').textContent).toBe('Ready');
  });

  it('drives the cursor via the scrubber and pauses playback', () => {
    seed(120, 500);
    useReplayStore.getState().setPlaybackStatus('playing');
    render(<ReplayTransportControls />);
    fireEvent.change(screen.getByTestId('replay-scrubber'), { target: { value: '250' } });
    expect(useReplayStore.getState().cursor?.sequence).toBe(250);
    expect(useReplayStore.getState().playbackStatus).toBe('paused');
  });

  it('steps forward and jumps to the range bounds', () => {
    seed(100, 500);
    render(<ReplayTransportControls />);
    fireEvent.click(screen.getByTestId('replay-step-forward'));
    expect(useReplayStore.getState().cursor?.sequence).toBe(101);
    fireEvent.click(screen.getByTestId('replay-jump-end'));
    expect(useReplayStore.getState().cursor?.sequence).toBe(500);
    fireEvent.click(screen.getByTestId('replay-jump-start'));
    expect(useReplayStore.getState().cursor?.sequence).toBe(0);
  });

  it('disables controls when the load status is unavailable', () => {
    seed(120, 500);
    useReplayStore.getState().setLoadStatus('unavailable');
    render(<ReplayTransportControls />);
    expect(screen.getByTestId('replay-scrubber')).toBeDisabled();
    expect(screen.getByTestId('replay-step-forward')).toBeDisabled();
  });
});
