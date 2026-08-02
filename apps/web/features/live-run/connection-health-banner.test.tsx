import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConnectionHealthState } from '@aegis/contracts-ts';

const { useLiveRun, useConnectionStatus, refetchQueries, resync } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
  useConnectionStatus: vi.fn(),
  refetchQueries: vi.fn(() => Promise.resolve()),
  resync: vi.fn(() => Promise.resolve()),
}));
vi.mock('@/features/live-run/live-run-provider', () => ({ useLiveRun }));
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useConnectionStatus,
}));
// The banner's manual retry reaches the cache directly; the shell owns the real provider.
vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ refetchQueries }),
}));

import { ConnectionHealthBanner, describeConnectionNotice } from './connection-health-banner';

function mockLive(health: string, isStale = false) {
  useLiveRun.mockReturnValue({
    isLiveMode: true,
    resync,
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

  it('mutes informational delivery narration once the run is terminal', () => {
    // A stopped run has nothing left to deliver — "Catching up" would otherwise sit on
    // screen forever, since no future event or resync arrives to clear it.
    // Not snapshot_resync: that one is a warning and always ends in CONNECTED, so it
    // cannot stick — and a resync genuinely running deserves its banner.
    for (const runStatus of ['stopped', 'completed']) {
      for (const health of [
        ConnectionHealthState.CATCHING_UP,
        ConnectionHealthState.SIMULATOR_PAUSED,
      ]) {
        expect(
          describeConnectionNotice({
            isLiveMode: true,
            health,
            isStale: false,
            connectionStatus: 'connected',
            runStatus,
          }),
        ).toBeNull();
      }
    }
  });

  it('keeps genuine fault warnings even on a terminal run', () => {
    expect(
      describeConnectionNotice({
        isLiveMode: true,
        health: ConnectionHealthState.DISCONNECTED,
        isStale: true,
        connectionStatus: 'connected',
        runStatus: 'stopped',
      }),
    ).toMatchObject({ key: 'disconnected', variant: 'warning' });
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

describe('ConnectionHealthBanner manual recovery', () => {
  it('offers a retry that refetches the active queries and resyncs the transport', () => {
    mockLive(ConnectionHealthState.DISCONNECTED);
    render(<ConnectionHealthBanner />);
    advance(700);

    // The operator is told the automatic retries have slowed down, not left guessing why
    // nothing is happening.
    expect(screen.getByTestId('connection-banner')).toHaveTextContent('Retries are backing off.');

    act(() => {
      screen.getByTestId('connection-retry-now').click();
    });

    expect(refetchQueries).toHaveBeenCalledWith({ type: 'active' });
    expect(resync).toHaveBeenCalledTimes(1);
  });

  it('offers it on a fixture-backed view too, where there is no transport to resync', () => {
    mockFixture('offline');
    render(<ConnectionHealthBanner />);
    advance(700);

    act(() => {
      screen.getByTestId('connection-retry-now').click();
    });

    expect(refetchQueries).toHaveBeenCalledWith({ type: 'active' });
    expect(resync).not.toHaveBeenCalled();
  });

  it('stays out of the way when the condition recovers on its own', () => {
    // A paused simulator resumes when the operator resumes it, and a catch-up finishes by
    // itself. A "Retry now" on either would do nothing and say something false.
    mockLive(ConnectionHealthState.SIMULATOR_PAUSED);
    render(<ConnectionHealthBanner />);
    advance(700);

    expect(screen.getByTestId('connection-banner')).toBeInTheDocument();
    expect(screen.queryByTestId('connection-retry-now')).toBeNull();
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
