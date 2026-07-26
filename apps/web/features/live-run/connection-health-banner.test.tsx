import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConnectionHealthState } from '@aegis/contracts-ts';

const { useLiveRun, useConnectionStatus } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
  useConnectionStatus: vi.fn(),
}));
vi.mock('@/features/live-run/live-run-provider', () => ({ useLiveRun }));
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useConnectionStatus,
}));

import { ConnectionHealthBanner, describeConnectionNotice } from './connection-health-banner';

function mockLive(health: string, isStale = false) {
  useLiveRun.mockReturnValue({
    isLiveMode: true,
    state: { connectionHealth: health, isStale, lastAppliedSequence: 42 },
  });
}

function mockFixture(status: 'connected' | 'reconnecting' | 'offline') {
  useLiveRun.mockReturnValue(null);
  useConnectionStatus.mockReturnValue({ data: status });
}

function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  useConnectionStatus.mockReturnValue({ data: 'connected' });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('describeConnectionNotice', () => {
  it('says nothing while a live run is healthy', () => {
    expect(
      describeConnectionNotice({
        isLiveMode: true,
        health: ConnectionHealthState.CONNECTED,
        isStale: false,
        connectionStatus: 'connected',
      }),
    ).toBeNull();
  });

  it('reports a stale projection even when the transport claims connected', () => {
    expect(
      describeConnectionNotice({
        isLiveMode: true,
        health: ConnectionHealthState.CONNECTED,
        isStale: true,
        connectionStatus: 'connected',
      }),
    ).toMatchObject({ key: 'stale' });
  });

  it('maps each degraded live health to its own notice', () => {
    for (const health of [
      ConnectionHealthState.DISCONNECTED,
      ConnectionHealthState.RECONNECTING,
      ConnectionHealthState.CATCHING_UP,
      ConnectionHealthState.SNAPSHOT_RESYNC,
      ConnectionHealthState.GAP,
      ConnectionHealthState.SIMULATOR_PAUSED,
      ConnectionHealthState.LOCALLY_PAUSED,
    ]) {
      expect(
        describeConnectionNotice({
          isLiveMode: true,
          health,
          isStale: false,
          connectionStatus: 'connected',
        }),
      ).toMatchObject({ key: health });
    }
  });

  it('falls back to the polled status outside live mode', () => {
    expect(
      describeConnectionNotice({
        isLiveMode: false,
        connectionStatus: 'connected',
      }),
    ).toBeNull();
    expect(
      describeConnectionNotice({
        isLiveMode: false,
        connectionStatus: 'offline',
      }),
    ).toMatchObject({ title: 'Connection offline' });
    expect(
      describeConnectionNotice({
        isLiveMode: false,
        connectionStatus: 'reconnecting',
      }),
    ).toMatchObject({ title: 'Reconnecting' });
  });
});

describe('ConnectionHealthBanner hysteresis', () => {
  it('stays silent while the run is healthy', () => {
    mockLive(ConnectionHealthState.CONNECTED);
    const { container } = render(<ConnectionHealthBanner />);
    advance(5_000);
    expect(container).toBeEmptyDOMElement();
  });

  it('ignores a transient resync blip that clears before the appearance delay', () => {
    mockLive(ConnectionHealthState.SNAPSHOT_RESYNC);
    const { rerender } = render(<ConnectionHealthBanner />);
    advance(400);
    expect(screen.queryByTestId('connection-banner')).toBeNull();

    mockLive(ConnectionHealthState.CONNECTED);
    rerender(<ConnectionHealthBanner />);
    advance(5_000);
    expect(screen.queryByTestId('connection-banner')).toBeNull();
  });

  it('shows the banner once the degraded state has persisted', () => {
    mockLive(ConnectionHealthState.DISCONNECTED);
    render(<ConnectionHealthBanner />);
    advance(699);
    expect(screen.queryByTestId('connection-banner')).toBeNull();
    advance(1);
    expect(screen.getByTestId('connection-banner')).toHaveAttribute(
      'data-connection-notice',
      'disconnected',
    );
  });

  it('does not restart the appearance delay when the degraded state changes shape', () => {
    mockLive(ConnectionHealthState.RECONNECTING);
    const { rerender } = render(<ConnectionHealthBanner />);
    advance(400);
    mockLive(ConnectionHealthState.GAP);
    rerender(<ConnectionHealthBanner />);
    advance(300);
    expect(screen.getByTestId('connection-banner')).toHaveAttribute(
      'data-connection-notice',
      'gap',
    );
  });

  it('holds the banner for a minimum window so recovery cannot make it blink', () => {
    mockLive(ConnectionHealthState.GAP);
    const { rerender } = render(<ConnectionHealthBanner />);
    advance(700);
    expect(screen.getByTestId('connection-banner')).toBeInTheDocument();

    mockLive(ConnectionHealthState.CONNECTED);
    rerender(<ConnectionHealthBanner />);
    advance(1_199);
    expect(screen.queryByTestId('connection-banner')).toBeInTheDocument();
    advance(1);
    expect(screen.queryByTestId('connection-banner')).toBeNull();
  });

  it('swaps copy in place when the condition changes while already shown', () => {
    mockLive(ConnectionHealthState.RECONNECTING);
    const { rerender } = render(<ConnectionHealthBanner />);
    advance(700);
    expect(screen.getByTestId('connection-banner')).toHaveAttribute(
      'data-connection-notice',
      'reconnecting',
    );

    mockLive(ConnectionHealthState.DISCONNECTED);
    rerender(<ConnectionHealthBanner />);
    expect(screen.getByTestId('connection-banner')).toHaveAttribute(
      'data-connection-notice',
      'disconnected',
    );
  });

  it('covers fixture-backed views from the same surface', () => {
    mockFixture('offline');
    render(<ConnectionHealthBanner />);
    advance(700);
    const banner = screen.getByTestId('connection-banner');
    expect(banner).toHaveAttribute('data-connection-notice', 'fixture_offline');
    expect(banner).toHaveTextContent('Showing last known fixture data.');
  });
});

describe('ConnectionHealthBanner layout neutrality', () => {
  it('occupies no height and overlays the content instead of displacing it', () => {
    mockLive(ConnectionHealthState.DISCONNECTED);
    render(<ConnectionHealthBanner />);
    advance(700);

    const slot = screen.getByTestId('connection-health-banner');
    // Zero-height, positioned slot: <main> below it can never be resized by a health flip.
    expect(slot.className).toContain('h-0');
    expect(slot.className).toContain('relative');

    const layer = slot.firstElementChild;
    expect(layer?.className).toContain('absolute');
    // The overlay itself must not swallow clicks aimed at the controls underneath it.
    expect(layer?.className).toContain('pointer-events-none');
    expect(screen.getByTestId('connection-banner').className).toContain('pointer-events-auto');
  });
});
