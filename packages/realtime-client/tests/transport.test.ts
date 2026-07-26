import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RealtimeTransport, type RealtimeTransportOptions } from '../src/transport';

const WS_URL = 'wss://aegis.test/ws';

interface FakeSocketOptions {
  /** Milliseconds the socket stays open after acknowledging the handshake. */
  lifetimeMs: number;
  /** When false the socket closes without ever sending `hello_ack`. */
  ackHandshake: boolean;
}

const fakeSocketOptions: FakeSocketOptions = {
  lifetimeMs: 0,
  ackHandshake: true,
};
let sockets: FakeSocket[] = [];

function utcNow(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, '.000Z');
}

function helloAckFrame(): string {
  return JSON.stringify({
    schemaVersion: 1,
    protocolVersion: 1,
    messageType: 'hello_ack',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAX',
    sentAt: utcNow(),
    payload: {
      protocolVersion: 1,
      connectionId: 'conn_test',
      principalId: 'user_test',
    },
  });
}

/**
 * Minimal WebSocket stand-in whose whole job is to reproduce the flapping
 * endpoint: connect, acknowledge the handshake, then die.
 */
class FakeSocket {
  static readonly OPEN = 1;

  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  readonly createdAt = Date.now();
  readonly behaviour: FakeSocketOptions = { ...fakeSocketOptions };
  closedAt: number | null = null;
  helloToken: string | null = null;

  private closed = false;

  constructor(readonly url: string) {
    sockets.push(this);
    setTimeout(() => {
      this.readyState = FakeSocket.OPEN;
      this.onopen?.();
    }, 0);
  }

  send(raw: string): void {
    const frame = JSON.parse(raw) as {
      messageType: string;
      payload: { authToken?: string | null };
    };
    if (frame.messageType !== 'hello') {
      return;
    }
    this.helloToken = frame.payload.authToken ?? null;
    if (!this.behaviour.ackHandshake) {
      setTimeout(() => {
        this.close();
      }, 0);
      return;
    }
    setTimeout(() => {
      this.onmessage?.({ data: helloAckFrame() });
      setTimeout(() => {
        this.close();
      }, this.behaviour.lifetimeMs);
    }, 0);
  }

  close(): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.readyState = 3;
    this.closedAt = Date.now();
    this.onclose?.();
  }
}

const WebSocketImpl = FakeSocket as unknown as typeof WebSocket;

/** Virtual-time delay actually waited between a socket dying and the next attempt. */
function retryDelays(): number[] {
  return sockets
    .slice(1)
    .map((socket, index) => socket.createdAt - (sockets[index]?.closedAt ?? 0));
}

function newTransport(overrides: Partial<RealtimeTransportOptions> = {}): RealtimeTransport {
  return new RealtimeTransport({
    url: WS_URL,
    autoReconnect: true,
    reconnectBackoff: {
      minDelayMs: 250,
      maxDelayMs: 30_000,
      multiplier: 2,
      jitterRatio: 0,
    },
    stableConnectionMs: 10_000,
    WebSocketImpl,
    ...overrides,
  });
}

describe('RealtimeTransport reconnect behaviour', () => {
  beforeEach(() => {
    vi.useFakeTimers({ now: 0 });
    sockets = [];
    fakeSocketOptions.lifetimeMs = 0;
    fakeSocketOptions.ackHandshake = true;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('backs off exponentially when every connection dies immediately', async () => {
    const transport = newTransport();
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(5_000);
    await connected;

    expect(retryDelays().slice(0, 4)).toEqual([250, 500, 1_000, 2_000]);

    transport.disconnect();
  });

  it('does not reset the backoff on the handshake alone', async () => {
    const transport = newTransport();
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(2_000);
    await connected;

    // Every attempt completed a handshake, so a hello_ack-only reset would
    // have held the delay at the 250ms floor forever.
    expect(retryDelays().at(-1)).toBeGreaterThan(250);

    transport.disconnect();
  });

  it('resets the backoff once a connection proves stable', async () => {
    const transport = newTransport();
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(2_000);
    await connected;
    expect(retryDelays().at(-1)).toBeGreaterThan(250);

    // Subsequent sockets hold well past stableConnectionMs before dropping.
    fakeSocketOptions.lifetimeMs = 20_000;
    await vi.advanceTimersByTimeAsync(60_000);

    expect(retryDelays().at(-1)).toBe(250);

    transport.disconnect();
  });

  it('settles connect() when the socket closes before hello_ack', async () => {
    fakeSocketOptions.ackHandshake = false;
    const transport = newTransport();

    let settled = false;
    const pending = transport.connect().then(() => {
      settled = true;
    });
    await vi.advanceTimersByTimeAsync(10);
    await pending;

    expect(settled).toBe(true);
    expect(transport.connectionState).toBe('reconnecting');

    transport.disconnect();
  });

  it('settles at the ceiling instead of hammering a permanently broken endpoint', async () => {
    fakeSocketOptions.ackHandshake = false;
    const transport = newTransport({
      reconnectBackoff: {
        minDelayMs: 100,
        maxDelayMs: 800,
        multiplier: 2,
        jitterRatio: 0,
      },
    });
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(120_000);
    await connected;

    const delays = retryDelays();
    expect(delays.length).toBeGreaterThan(5);
    for (const delay of delays) {
      expect(delay).toBeLessThanOrEqual(800);
    }
    expect(delays.at(-1)).toBe(800);

    transport.disconnect();
  });

  it('stops reconnecting once disconnect() is called', async () => {
    const transport = newTransport();
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(1_000);
    await connected;

    transport.disconnect();
    const countAtDisconnect = sockets.length;
    await vi.advanceTimersByTimeAsync(60_000);

    expect(sockets.length).toBe(countAtDisconnect);
    expect(transport.connectionState).toBe('closed');
  });
});

describe('RealtimeTransport credentials', () => {
  beforeEach(() => {
    vi.useFakeTimers({ now: 0 });
    sockets = [];
    fakeSocketOptions.lifetimeMs = 0;
    fakeSocketOptions.ackHandshake = true;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('replays the static token when no provider is supplied', async () => {
    const transport = newTransport({ token: 'ticket-static' });
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(1_000);
    await connected;

    expect(sockets.length).toBeGreaterThan(1);
    for (const socket of sockets) {
      expect(socket.helloToken).toBe('ticket-static');
    }

    transport.disconnect();
  });

  it('mints a fresh token for every connection attempt', async () => {
    let issued = 0;
    const getToken = vi.fn(() => {
      issued += 1;
      return Promise.resolve(`ticket-${String(issued)}`);
    });
    // A stale token would be replayed here; WS tickets are single-shot with a
    // 5-minute TTL, so a reconnect past that window must re-authenticate.
    const transport = newTransport({ token: 'ticket-stale', getToken });
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(2_000);
    await connected;

    expect(sockets.length).toBeGreaterThan(2);
    expect(sockets.map((socket) => socket.helloToken)).toEqual(
      sockets.map((_socket, index) => `ticket-${String(index + 1)}`),
    );
    expect(getToken).toHaveBeenCalledTimes(sockets.length);

    transport.disconnect();
  });

  it('backs off instead of wedging when the token provider rejects', async () => {
    const attemptedAt: number[] = [];
    const getToken = vi.fn(() => {
      attemptedAt.push(Date.now());
      return Promise.reject(new Error('ws-ticket unavailable'));
    });
    const transport = newTransport({ getToken });
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(5_000);
    await connected;

    // No socket is ever opened, but the transport keeps trying on the backoff.
    expect(sockets).toHaveLength(0);
    expect(attemptedAt.length).toBeGreaterThanOrEqual(4);
    const gaps = attemptedAt.slice(1).map((at, index) => at - (attemptedAt[index] ?? 0));
    expect(gaps.slice(0, 4)).toEqual([250, 500, 1_000, 2_000]);
    expect(transport.connectionState).toBe('reconnecting');

    transport.disconnect();
  });

  it('treats an empty token as a failed attempt', async () => {
    const getToken = vi.fn(() => Promise.resolve(null));
    const transport = newTransport({ getToken });
    const connected = transport.connect();
    await vi.advanceTimersByTimeAsync(2_000);
    await connected;

    expect(sockets).toHaveLength(0);
    expect(getToken.mock.calls.length).toBeGreaterThan(2);
    expect(transport.connectionState).toBe('reconnecting');

    transport.disconnect();
  });

  it('does not open a socket when disconnect() lands while a token is in flight', async () => {
    const getToken = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          setTimeout(() => {
            resolve('ticket-late');
          }, 100);
        }),
    );
    const transport = newTransport({ getToken });
    const connected = transport.connect();

    transport.disconnect();
    await vi.advanceTimersByTimeAsync(5_000);
    await connected;

    expect(sockets).toHaveLength(0);
    expect(transport.connectionState).toBe('closed');
  });
});
