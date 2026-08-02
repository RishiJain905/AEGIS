/**
 * Request-budget regressions for the live run provider.
 *
 * QA watched one browser tab issue 192 rate-limited requests against a single run in seconds.
 * The mechanism was a loop rather than a fast poll: live events arriving during a snapshot
 * resync were dropped, a dropped sequence makes the next event look like a gap, a gap asks
 * for a resync, and nothing paced or caught the failures in between. These tests pin the
 * three properties that break the loop — hold instead of drop, one resync at a time, and back
 * off while failing.
 */

import type { ReactNode } from 'react';

import type { DomainEventEnvelopeV1, RealtimeMessageEnvelopeV1 } from '@aegis/contracts-ts';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const buildBootstrapFromEndpoints = vi.fn();
vi.mock('@/lib/realtime/snapshot-resync', () => ({
  buildBootstrapFromEndpoints: (runId: string, signal?: AbortSignal) =>
    buildBootstrapFromEndpoints(runId, signal) as unknown,
}));

const fetchMissingEvents = vi.fn();
vi.mock('@/lib/realtime/catch-up', () => ({
  fetchMissingEvents: (...args: unknown[]) => fetchMissingEvents(...args) as unknown,
}));

vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: vi.fn(),
  apiFetchJson: vi.fn(() => Promise.resolve({ ticket: 'tkt_x' })),
}));

/** Hooks the provider registers on the transport, captured so tests can fire events. */
const listeners = new Map<string, (payload: unknown) => void>();
const connect = vi.fn(() => Promise.resolve());

vi.mock('@aegis/realtime-client', () => ({
  RealtimeTransport: class {
    on(event: string, handler: (payload: unknown) => void): () => void {
      listeners.set(event, handler);
      return () => listeners.delete(event);
    }
    connect = connect;
    subscribe = vi.fn();
    disconnect = vi.fn();
  },
}));

import { LiveRunProvider, useLiveRun } from './live-run-provider';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

const OTHER_RUN_ID = 'run_02BSA4PEFKTVW5SSGGRA7AH6BW';

function bootstrapPayload(lastAppliedSequence: number, runId: string = RUN_ID) {
  return {
    schemaVersion: 1,
    run: {
      schemaVersion: 1,
      id: runId,
      scenarioVersionId: 'scenario-version:1.0.0',
      seed: 1,
      status: 'running',
      startedAt: '2026-01-01T00:00:00Z',
      simTime: '2026-01-01T00:01:00Z',
      revision: 1,
    },
    graphSnapshot: {
      schemaVersion: 1,
      runId,
      sequence: lastAppliedSequence,
      revision: lastAppliedSequence,
      capturedAt: '2026-01-01T00:01:00Z',
      nodes: [],
      edges: [],
    },
    lastAppliedSequence,
  };
}

function envelope(sequence: number): RealtimeMessageEnvelopeV1 {
  const suffix = String(sequence).padStart(26, '0');
  return {
    schemaVersion: 1,
    channel: 'events',
    event: {
      schemaVersion: 1,
      eventId: `evt_${suffix}`,
      runId: RUN_ID,
      sequence,
      type: 'telemetry.api.request',
      simTime: '2026-01-01T00:01:00.000Z',
      recordedAt: '2026-06-30T02:00:01.102Z',
      actor: { type: 'asset', id: 'asset:device-workstation-01' },
      subject: { type: 'asset', id: 'asset:vpn-gw' },
      payload: { schemaVersion: 1 },
      traceId: `trc_${suffix}`,
      correlationId: null,
      causationId: null,
    } as unknown as DomainEventEnvelopeV1,
  } as unknown as RealtimeMessageEnvelopeV1;
}

function emit(sequence: number): void {
  listeners.get('event')?.(envelope(sequence));
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <LiveRunProvider runId={RUN_ID}>{children}</LiveRunProvider>
    </QueryClientProvider>
  );
}

async function mountAndSettle(): Promise<void> {
  render(<div data-testid="child" />, { wrapper });
  await waitFor(() => {
    expect(listeners.has('event')).toBe(true);
  });
  await waitFor(() => {
    expect(buildBootstrapFromEndpoints).toHaveBeenCalled();
  });
  // Let the bootstrap's own promise chain settle before any event is fired.
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.stubEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'api');
  buildBootstrapFromEndpoints.mockResolvedValue(bootstrapPayload(10));
  fetchMissingEvents.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  listeners.clear();
  vi.clearAllMocks();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe('LiveRunProvider request budget', () => {
  it('bootstraps once per mount even when events arrive mid-bootstrap', async () => {
    // The WebSocket connects in parallel with the bootstrap. An event landing while the
    // sequence cursor is still zero used to read as a gap and trigger a second bootstrap on
    // every single mount.
    let releaseBootstrap: (value: unknown) => void = () => undefined;
    buildBootstrapFromEndpoints.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          releaseBootstrap = resolve;
        }),
    );

    render(<div />, { wrapper });
    await waitFor(() => {
      expect(listeners.has('event')).toBe(true);
    });

    act(() => {
      emit(40);
      emit(41);
    });
    await act(async () => {
      releaseBootstrap(bootstrapPayload(10));
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(buildBootstrapFromEndpoints).toHaveBeenCalledTimes(1);
    });
  });

  it('holds a burst of gaps to a single resync rather than one per event', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await mountAndSettle();

    // Every one of these marked a gap, and every gap used to fire its own resync — three
    // requests apiece — the moment it was seen.
    act(() => {
      for (let sequence = 40; sequence < 60; sequence += 1) {
        emit(sequence);
      }
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });

    // One bootstrap for the mount, one for the whole burst.
    expect(buildBootstrapFromEndpoints).toHaveBeenCalledTimes(2);
  });

  it('does not resync again inside the backoff window after one that failed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await mountAndSettle();

    buildBootstrapFromEndpoints.mockRejectedValue(new Error('rate limited'));

    // First gap: one resync attempt, which fails.
    act(() => {
      emit(40);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const afterFirstFailure = buildBootstrapFromEndpoints.mock.calls.length;
    expect(afterFirstFailure).toBe(2);

    // Every subsequent event inside the (now doubled) backoff window must cost nothing.
    // Before the fix each of these was another bootstrap — and, when that 429'd, another two
    // requests behind it.
    act(() => {
      for (let sequence = 41; sequence < 80; sequence += 1) {
        emit(sequence);
      }
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(buildBootstrapFromEndpoints.mock.calls.length).toBe(afterFirstFailure);

    // And it does try again once the window has actually elapsed — backed off, not given up.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(buildBootstrapFromEndpoints.mock.calls.length).toBe(afterFirstFailure + 1);
  });

  it('applies events held during a resync instead of dropping them into a fresh gap', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await mountAndSettle();

    // Resync to a head of 42, with the events that arrive mid-flight continuing from there.
    let releaseResync: (value: unknown) => void = () => undefined;
    buildBootstrapFromEndpoints.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          releaseResync = resolve;
        }),
    );

    act(() => {
      emit(40);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    expect(buildBootstrapFromEndpoints).toHaveBeenCalledTimes(2);

    // Arrives while the snapshot is still being fetched. Dropping it would leave the client
    // one sequence short forever, and the next event would start the loop again.
    act(() => {
      emit(43);
    });
    await act(async () => {
      releaseResync(bootstrapPayload(42));
      await vi.advanceTimersByTimeAsync(5_000);
    });

    // The held event applied contiguously on top of the resync, so nothing asked for a third.
    expect(buildBootstrapFromEndpoints).toHaveBeenCalledTimes(2);
  });

  it('discards a resync that lands after the operator moved to another run', async () => {
    // The shell mounts this provider once and swaps the `runId` prop, so every ref it holds
    // survives the move. A resync still in flight for the run just left would otherwise
    // finish and load that run's graph over the one now on screen.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    buildBootstrapFromEndpoints.mockImplementation((runId: string) =>
      Promise.resolve(bootstrapPayload(10, runId)),
    );

    function ShownRun() {
      const liveRun = useLiveRun();
      return <span data-testid="snapshot-run">{liveRun?.bootstrapSnapshot?.runId ?? 'none'}</span>;
    }

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const tree = (runId: string) => (
      <QueryClientProvider client={client}>
        <LiveRunProvider runId={runId}>
          <ShownRun />
        </LiveRunProvider>
      </QueryClientProvider>
    );

    const { rerender } = render(tree(RUN_ID));
    await waitFor(() => {
      expect(screen.getByTestId('snapshot-run')).toHaveTextContent(RUN_ID);
    });

    // A gap on the first run puts a resync in flight, and hold it there.
    let releaseResync: (value: unknown) => void = () => undefined;
    buildBootstrapFromEndpoints.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          releaseResync = resolve;
        }),
    );
    act(() => {
      emit(40);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    expect(buildBootstrapFromEndpoints).toHaveBeenCalledTimes(2);

    rerender(tree(OTHER_RUN_ID));
    await waitFor(() => {
      expect(screen.getByTestId('snapshot-run')).toHaveTextContent(OTHER_RUN_ID);
    });

    // The abandoned run's resync finally answers.
    await act(async () => {
      releaseResync(bootstrapPayload(10, RUN_ID));
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(screen.getByTestId('snapshot-run')).toHaveTextContent(OTHER_RUN_ID);
  });
});
