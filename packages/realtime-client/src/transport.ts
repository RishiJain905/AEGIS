import {
  PROTOCOL_VERSION_V1,
  parseContract,
  websocketErrorPayloadSchema,
  websocketEventPayloadSchema,
  websocketFrameSchema,
  websocketPingPayloadSchema,
  websocketResyncCompletePayloadSchema,
  websocketSnapshotRequiredPayloadSchema,
  websocketWarningPayloadSchema,
  type RealtimeMessageEnvelopeV1,
  type WebSocketFrameV1,
  type WebSocketSnapshotRequiredPayloadV1,
} from '@aegis/contracts-ts';

import type { RealtimeConnectionState, SubscriptionCursor } from './connection-state';
import { computeReconnectDelayMs, type ReconnectBackoffOptions } from './reconnect';

export interface RealtimeTransportOptions {
  url: string;
  token?: string;
  autoReconnect?: boolean;
  reconnectBackoff?: ReconnectBackoffOptions;
  /**
   * How long a connection must survive after `hello_ack` before it counts as
   * stable and the reconnect backoff counter is reset. Resetting on the
   * handshake alone pins a flapping endpoint at the minimum delay forever.
   */
  stableConnectionMs?: number;
  /**
   * Resolves a fresh auth token for every connection attempt. Required for
   * credentials that expire: the WebSocket ticket is single-shot with a
   * 5-minute TTL, so replaying the token captured at construction time makes
   * every reconnect after that window fail with `SESSION_EXPIRED` forever.
   * Takes precedence over `token`; a rejection or an empty result fails the
   * attempt and falls through to the normal backoff.
   */
  getToken?: () => Promise<string | null>;
  WebSocketImpl?: typeof WebSocket;
}

export type RealtimeTransportEventMap = {
  connection_state: RealtimeConnectionState;
  event: RealtimeMessageEnvelopeV1;
  error: { code: string; message: string };
  snapshot_required: WebSocketSnapshotRequiredPayloadV1;
  resync_complete: {
    runId: string;
    toSequence: number;
    eventsDelivered: number;
  };
  warning: { code: string; message: string };
};

type EventKey = keyof RealtimeTransportEventMap;
type EventHandler<K extends EventKey> = (payload: RealtimeTransportEventMap[K]) => void;

/** `WebSocket.OPEN`, inlined so the transport does not depend on a global. */
const WEBSOCKET_OPEN = 1;

/** A connection has to hold this long past `hello_ack` before backoff resets. */
const DEFAULT_STABLE_CONNECTION_MS = 10_000;

/**
 * Ceiling on the backoff exponent. `computeReconnectDelayMs` already clamps to
 * `maxDelayMs`; capping the counter keeps the exponent finite so a permanently
 * broken endpoint settles at the maximum delay instead of overflowing.
 */
const MAX_RECONNECT_ATTEMPT = 12;

function newTraceId(): string {
  const alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  let body = '';
  for (let i = 0; i < 26; i++) {
    body += alphabet[Math.floor(Math.random() * alphabet.length)] ?? '0';
  }
  return `trc_${body}`;
}

function utcNow(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, '.000Z');
}

export class RealtimeTransport {
  private readonly options: RealtimeTransportOptions;
  private readonly handlers: {
    [K in EventKey]: Set<EventHandler<K>>;
  } = {
    connection_state: new Set(),
    event: new Set(),
    error: new Set(),
    snapshot_required: new Set(),
    resync_complete: new Set(),
    warning: new Set(),
  };

  private socket: WebSocket | null = null;
  private state: RealtimeConnectionState = 'disconnected';
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stabilityTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  private cursors = new Map<string, SubscriptionCursor>();
  private seenEventIds = new Set<string>();

  constructor(options: RealtimeTransportOptions) {
    this.options = options;
  }

  on<K extends EventKey>(event: K, handler: EventHandler<K>): () => void {
    this.handlers[event].add(handler);
    return () => this.handlers[event].delete(handler);
  }

  get connectionState(): RealtimeConnectionState {
    return this.state;
  }

  get subscriptions(): SubscriptionCursor[] {
    return [...this.cursors.values()];
  }

  async connect(): Promise<void> {
    this.intentionalClose = false;
    try {
      await this.openSocket(false);
    } catch {
      // A failed initial connection is reported through `connection_state`; it
      // must never reject into the caller's render/effect path.
      this.handleOpenFailure();
    }
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.clearStabilityTimer();
    this.socket?.close();
    this.socket = null;
    this.setState('closed');
  }

  subscribe(cursor: SubscriptionCursor): void {
    const key = `${cursor.runId}:${cursor.channel}`;
    this.cursors.set(key, { ...cursor });
    if (this.socket?.readyState === WEBSOCKET_OPEN) {
      this.sendFrame('subscribe', {
        runId: cursor.runId,
        channel: cursor.channel,
        lastAppliedSequence: cursor.lastAppliedSequence,
      });
    }
  }

  /**
   * Resolve the credential for a single attempt. Throwing here is the same
   * class of failure as a socket that will not open: the caller routes it into
   * `handleOpenFailure`, so a temporarily unreachable ticket endpoint keeps
   * retrying on the backoff instead of wedging the transport.
   */
  private async resolveAuthToken(): Promise<string | null> {
    const provider = this.options.getToken;
    if (!provider) {
      return this.options.token ?? null;
    }
    const token = await provider();
    if (!token) {
      throw new Error('Realtime auth token provider returned no token');
    }
    return token;
  }

  private async openSocket(isReconnect: boolean): Promise<void> {
    this.setState(isReconnect ? 'reconnecting' : 'connecting');
    // Resolved before the socket exists so a credential failure never leaves a
    // half-open connection behind.
    const authToken = await this.resolveAuthToken();
    if (this.intentionalClose) {
      // Torn down while the credential was in flight; opening now would leak a
      // socket nobody owns.
      return;
    }
    const WebSocketImpl = this.options.WebSocketImpl ?? WebSocket;
    const socket = new WebSocketImpl(this.options.url);
    this.socket = socket;

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const settleResolve = (): void => {
        if (settled) {
          return;
        }
        settled = true;
        resolve();
      };
      const settleReject = (error: Error): void => {
        if (settled) {
          return;
        }
        settled = true;
        reject(error);
      };

      socket.onopen = () => {
        this.sendRaw(
          this.buildFrame('hello', {
            protocolVersion: PROTOCOL_VERSION_V1,
            authToken,
          }),
        );
      };

      socket.onmessage = (event) => {
        try {
          const frame = parseContract(websocketFrameSchema, JSON.parse(String(event.data)));
          this.handleFrame(frame, settleResolve);
        } catch (error) {
          settleReject(error instanceof Error ? error : new Error(String(error)));
        }
      };

      socket.onerror = () => {
        settleReject(new Error('WebSocket connection failed'));
      };

      socket.onclose = () => {
        this.clearStabilityTimer();
        if (this.socket === socket) {
          this.socket = null;
        }
        if (this.intentionalClose) {
          this.setState('closed');
          settleResolve();
          return;
        }
        this.scheduleReconnect();
        // Always settle: a socket that dies before `hello_ack` used to leave
        // this promise (and therefore `connect()`) pending forever.
        settleResolve();
      };
    });
  }

  private handleFrame(frame: WebSocketFrameV1, onConnected: () => void): void {
    switch (frame.messageType) {
      case 'hello_ack':
        this.setState('connected');
        this.startStabilityTimer();
        onConnected();
        for (const cursor of this.cursors.values()) {
          this.sendFrame('subscribe', {
            runId: cursor.runId,
            channel: cursor.channel,
            lastAppliedSequence: cursor.lastAppliedSequence,
          });
        }
        return;
      case 'ping': {
        const pingPayload = parseContract(websocketPingPayloadSchema, frame.payload);
        this.sendFrame('pong', { serverTime: pingPayload.serverTime });
        return;
      }
      case 'event': {
        const eventPayload = parseContract(websocketEventPayloadSchema, frame.payload);
        const envelope = eventPayload.envelope;
        if (this.seenEventIds.has(envelope.event.eventId)) {
          this.emit('warning', {
            code: 'WS_DUPLICATE_SUPPRESSED',
            message: 'Duplicate event suppressed',
          });
          return;
        }
        this.seenEventIds.add(envelope.event.eventId);
        const key = `${envelope.event.runId}:${envelope.channel}`;
        const cursor = this.cursors.get(key);
        if (cursor) {
          cursor.lastAppliedSequence = Math.max(
            cursor.lastAppliedSequence,
            envelope.event.sequence,
          );
        }
        this.emit('event', envelope);
        return;
      }
      case 'error': {
        const errorPayload = parseContract(websocketErrorPayloadSchema, frame.payload);
        this.emit('error', {
          code: errorPayload.error.code,
          message: errorPayload.error.message,
        });
        return;
      }
      case 'snapshot_required': {
        const snapshotPayload = parseContract(
          websocketSnapshotRequiredPayloadSchema,
          frame.payload,
        );
        this.emit('snapshot_required', snapshotPayload);
        return;
      }
      case 'resync_complete': {
        const resyncPayload = parseContract(websocketResyncCompletePayloadSchema, frame.payload);
        this.emit('resync_complete', {
          runId: resyncPayload.runId,
          toSequence: resyncPayload.toSequence,
          eventsDelivered: resyncPayload.eventsDelivered,
        });
        return;
      }
      case 'warning': {
        const warningPayload = parseContract(websocketWarningPayloadSchema, frame.payload);
        this.emit('warning', {
          code: warningPayload.code,
          message: warningPayload.message,
        });
        return;
      }
      default:
        return;
    }
  }

  /**
   * Reset the backoff only once a connection has proven itself. A handshake
   * that succeeds and then drops a moment later is not a healthy connection —
   * treating it as one pins the delay at the floor and turns a flapping
   * endpoint into a request storm.
   */
  private startStabilityTimer(): void {
    this.clearStabilityTimer();
    const stableAfterMs = this.options.stableConnectionMs ?? DEFAULT_STABLE_CONNECTION_MS;
    if (stableAfterMs <= 0) {
      this.reconnectAttempt = 0;
      return;
    }
    this.stabilityTimer = setTimeout(() => {
      this.stabilityTimer = null;
      this.reconnectAttempt = 0;
    }, stableAfterMs);
  }

  /**
   * Recover from an `openSocket` rejection. If the socket is still around (an
   * unparseable frame rather than a dead connection) close it first so exactly
   * one retry is scheduled, from `onclose`.
   */
  private handleOpenFailure(): void {
    const socket = this.socket;
    if (socket) {
      socket.close();
      return;
    }
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.intentionalClose) {
      // disconnect() already published 'closed'; a late failure from an
      // in-flight attempt must not resurrect the connection or the state.
      return;
    }
    if (!this.options.autoReconnect) {
      this.setState('disconnected');
      return;
    }
    if (this.reconnectTimer !== null) {
      // A retry is already pending for this connection cycle. Sockets commonly
      // report `error` and `close` for the same failure; only one of those may
      // advance the attempt counter.
      return;
    }
    this.reconnectAttempt = Math.min(this.reconnectAttempt + 1, MAX_RECONNECT_ATTEMPT);
    const delay = computeReconnectDelayMs(this.reconnectAttempt, this.options.reconnectBackoff);
    this.setState('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.openSocket(true).catch(() => {
        this.handleOpenFailure();
      });
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearStabilityTimer(): void {
    if (this.stabilityTimer !== null) {
      clearTimeout(this.stabilityTimer);
      this.stabilityTimer = null;
    }
  }

  private setState(state: RealtimeConnectionState): void {
    this.state = state;
    this.emit('connection_state', state);
  }

  private buildFrame(messageType: string, payload: Record<string, unknown>): string {
    return JSON.stringify({
      schemaVersion: 1,
      protocolVersion: PROTOCOL_VERSION_V1,
      messageType,
      traceId: newTraceId(),
      sentAt: utcNow(),
      payload,
    });
  }

  private sendFrame(messageType: string, payload: Record<string, unknown>): void {
    this.sendRaw(this.buildFrame(messageType, payload));
  }

  private sendRaw(raw: string): void {
    if (this.socket?.readyState === WEBSOCKET_OPEN) {
      this.socket.send(raw);
    }
  }

  private emit<K extends EventKey>(event: K, payload: RealtimeTransportEventMap[K]): void {
    for (const handler of this.handlers[event]) {
      handler(payload);
    }
  }
}
