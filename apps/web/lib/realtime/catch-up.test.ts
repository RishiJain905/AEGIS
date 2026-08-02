import { afterEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

import { EVENT_PAGE_LIMIT, fetchMissingEvents } from './catch-up';

interface StubEvent {
  schemaVersion: number;
  eventId: string;
  runId: string;
  sequence: number;
  type: string;
  simTime: string;
  recordedAt: string;
  actor: { type: string; id: string };
  subject: { type: string; id: string };
  payload: Record<string, unknown>;
  traceId: string;
  correlationId: null;
  causationId: null;
}

function stubEvent(sequence: number): StubEvent {
  const suffix = String(sequence).padStart(26, '0');
  return {
    schemaVersion: 1,
    eventId: `evt_${suffix}`,
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    sequence,
    type: 'telemetry.api.request',
    simTime: '2026-01-01T00:00:00.000Z',
    recordedAt: '2026-06-30T02:00:01.102Z',
    actor: { type: 'asset', id: 'asset:device-workstation-01' },
    subject: { type: 'asset', id: 'asset:vpn-gw' },
    payload: { schemaVersion: 1 },
    traceId: `trc_${suffix}`,
    correlationId: null,
    causationId: null,
  };
}

function respondWith(events: StubEvent[]): Response {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ events }),
  } as unknown as Response;
}

function requestedFromSequences(): number[] {
  return apiFetch.mock.calls.map((call) => {
    const url = new URL(`http://api${String(call[0])}`);
    return Number(url.searchParams.get('from_sequence'));
  });
}

afterEach(() => {
  apiFetch.mockReset();
});

describe('fetchMissingEvents', () => {
  it('walks every page until the run head is reached', async () => {
    const firstPage = Array.from({ length: EVENT_PAGE_LIMIT }, (_, index) => stubEvent(index + 1));
    const secondPage = [stubEvent(EVENT_PAGE_LIMIT + 1), stubEvent(EVENT_PAGE_LIMIT + 2)];
    apiFetch
      .mockResolvedValueOnce(respondWith(firstPage))
      .mockResolvedValueOnce(respondWith(secondPage));

    const events = await fetchMissingEvents(
      'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      1,
      EVENT_PAGE_LIMIT + 2,
    );

    // The single-page version stopped at 500 and left the client permanently behind its run,
    // so the next live event read as a gap and asked for yet another resync.
    expect(events).toHaveLength(EVENT_PAGE_LIMIT + 2);
    expect(events.at(-1)?.sequence).toBe(EVENT_PAGE_LIMIT + 2);
    expect(requestedFromSequences()).toEqual([1, EVENT_PAGE_LIMIT + 1]);
  });

  it('stops at the requested head rather than following the stream past it', async () => {
    apiFetch.mockResolvedValueOnce(respondWith([stubEvent(4), stubEvent(5), stubEvent(6)]));

    const events = await fetchMissingEvents('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', 4, 5);

    expect(events.map((event) => event.sequence)).toEqual([4, 5]);
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it('gives up when a page fails to advance the cursor', async () => {
    // A server that keeps answering with the same sequences would otherwise be asked
    // forever — the request amplifier this whole change exists to remove.
    apiFetch.mockResolvedValue(respondWith([stubEvent(1)]));

    const events = await fetchMissingEvents('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', 2, 900);

    expect(events).toEqual([]);
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it('makes no request when the snapshot already covers the head', async () => {
    const events = await fetchMissingEvents('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', 11, 10);

    expect(events).toEqual([]);
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
