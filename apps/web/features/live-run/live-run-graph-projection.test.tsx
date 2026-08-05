/**
 * Live-board projection regressions for the live run provider.
 *
 * QA executed a containment, watched the API settle on `contained` with
 * `appliedControls: ["observed", "isolated"]`, and watched the inspector and the console
 * chip keep narrating the pre-isolate posture for the next half minute. Resync fixed it
 * instantly, which acquits the projector and the server and puts the fault squarely on the
 * live delta path.
 *
 * The mechanism these tests pin: graph deltas are a *sparse* projection of the run's event
 * stream. Telemetry, alerts, agent turns and approvals all consume sequence numbers and
 * change no graph entity, so the store's applied-sequence cursor sits far behind the run
 * head, and the one delta that matters arrives hundreds of sequences ahead of it.
 */

import type { ReactNode } from 'react';

import type {
  DomainEventEnvelopeV1,
  GraphSnapshotV1,
  RealtimeMessageEnvelopeV1,
} from '@aegis/contracts-ts';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, waitFor } from '@testing-library/react';
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

const listeners = new Map<string, (payload: unknown) => void>();

vi.mock('@aegis/realtime-client', () => ({
  RealtimeTransport: class {
    on(event: string, handler: (payload: unknown) => void): () => void {
      listeners.set(event, handler);
      return () => listeners.delete(event);
    }
    connect = vi.fn(() => Promise.resolve());
    subscribe = vi.fn();
    disconnect = vi.fn();
  },
}));

import { LiveRunProvider, useLiveRun } from './live-run-provider';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const ASSET_ID = 'asset:svc-identity-broker';

function node(overrides: Partial<GraphSnapshotV1['nodes'][number]> = {}) {
  return {
    schemaVersion: 1,
    id: ASSET_ID,
    entityType: 'asset',
    assetType: 'service',
    label: 'Identity Broker',
    clusterId: null,
    riskScore: 0.4,
    criticality: 0.9,
    status: 'compromised',
    revision: 3,
    appliedControls: [],
    ...overrides,
  } as GraphSnapshotV1['nodes'][number];
}

function bootstrapPayload(snapshotSequence: number, headSequence: number) {
  return {
    schemaVersion: 1,
    run: {
      schemaVersion: 1,
      id: RUN_ID,
      scenarioVersionId: 'scenario-version:1.0.0',
      seed: 1,
      status: 'running',
      startedAt: '2026-01-01T00:00:00Z',
      simTime: '2026-01-01T00:01:00Z',
      revision: 1,
    },
    graphSnapshot: {
      schemaVersion: 1,
      runId: RUN_ID,
      sequence: snapshotSequence,
      revision: snapshotSequence,
      capturedAt: '2026-01-01T00:01:00Z',
      nodes: [node()],
      edges: [],
    },
    lastAppliedSequence: headSequence,
  };
}

function eventEnvelope(
  sequence: number,
  type: string,
  payload: Record<string, unknown> = {},
): RealtimeMessageEnvelopeV1 {
  const suffix = String(sequence).padStart(26, '0');
  return {
    schemaVersion: 1,
    channel: 'events',
    event: {
      schemaVersion: 1,
      eventId: `evt_${suffix}`,
      runId: RUN_ID,
      sequence,
      type,
      simTime: '2026-01-01T00:01:00.000Z',
      recordedAt: '2026-06-30T02:00:01.102Z',
      actor: { type: 'system', id: 'asset:simulator' },
      subject: { type: 'asset', id: ASSET_ID },
      payload: { schemaVersion: 1, ...payload },
      traceId: `trc_${suffix}`,
      correlationId: null,
      causationId: null,
    } as unknown as DomainEventEnvelopeV1,
  } as unknown as RealtimeMessageEnvelopeV1;
}

/** Reads the projection the inspector and the status strip actually render from. */
let liveNodes: GraphSnapshotV1['nodes'] = [];

function nodeById(id: string): GraphSnapshotV1['nodes'][number] | undefined {
  return liveNodes.find((entry) => entry.id === id);
}

function Probe() {
  const liveRun = useLiveRun();
  liveNodes =
    liveRun === null || liveRun.bootstrapSnapshot === null
      ? []
      : liveRun.graphStore.exportSnapshot().nodes;
  return null;
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
  render(<Probe />, { wrapper });
  await waitFor(() => {
    expect(listeners.has('event')).toBe(true);
  });
  await waitFor(() => {
    expect(buildBootstrapFromEndpoints).toHaveBeenCalled();
  });
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.stubEnv('NEXT_PUBLIC_AEGIS_DATA_SOURCE', 'api');
  buildBootstrapFromEndpoints.mockResolvedValue(bootstrapPayload(470, 470));
  fetchMissingEvents.mockResolvedValue([]);
  liveNodes = [];
});

afterEach(() => {
  cleanup();
  listeners.clear();
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});

describe('LiveRunProvider live graph projection', () => {
  it('applies a containment that lands far past the snapshot the store was seeded with', async () => {
    await mountAndSettle();
    expect(nodeById(ASSET_ID)?.status).toBe('compromised');

    // The run head races ahead of the graph snapshot on events that touch no graph entity.
    act(() => {
      for (let sequence = 471; sequence <= 660; sequence += 1) {
        listeners.get('event')?.(eventEnvelope(sequence, 'telemetry.api.request'));
      }
    });

    // The executed containment. Its sequence is 190 ahead of the snapshot the store loaded,
    // and every sequence in between belongs to an event that produced no delta.
    act(() => {
      listeners.get('event')?.(
        eventEnvelope(661, 'sim.asset.status_changed', {
          assetId: ASSET_ID,
          status: 'isolated',
        }),
      );
    });

    await waitFor(() => {
      expect(nodeById(ASSET_ID)?.appliedControls).toEqual(['isolated']);
    });
    expect(nodeById(ASSET_ID)?.status).toBe('contained');
  });

  it('applies every node update carried by one risk projection event', async () => {
    // A single event legitimately mutates several nodes. They all share its sequence, so a
    // per-delta cursor bump makes the store discard every one after the first.
    buildBootstrapFromEndpoints.mockResolvedValue({
      ...bootstrapPayload(470, 470),
      graphSnapshot: {
        ...bootstrapPayload(470, 470).graphSnapshot,
        nodes: [node(), node({ id: 'asset:database-customer-pii', label: 'Customer PII' })],
      },
    });
    await mountAndSettle();

    act(() => {
      listeners.get('event')?.(
        eventEnvelope(471, 'risk.projection.updated', {
          nodeUpdates: [
            { assetId: ASSET_ID, riskScore: 0.81, revision: 9 },
            { assetId: 'asset:database-customer-pii', riskScore: 0.77, revision: 9 },
          ],
        }),
      );
    });

    await waitFor(() => {
      expect(nodeById(ASSET_ID)?.riskScore).toBeCloseTo(0.81);
    });
    expect(nodeById('asset:database-customer-pii')?.riskScore).toBeCloseTo(0.77);
  });
});
