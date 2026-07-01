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
  WebSocketImpl?: typeof WebSocket;
}

export type RealtimeTransportEventMap = {
  connection_state: RealtimeConnectionState;
  event: RealtimeMessageEnvelopeV1;
  error: { code: string; message: string };
  snapshot_required: WebSocketSnapshotRequiredPayloadV1;
  resync_complete: { runId: string; toSequence: number; eventsDelivered: number };
  warning: { code: string; message: string };
};

type EventKey = keyof RealtimeTransportEventMap;
type EventHandler<K extends EventKey> = (payload: RealtimeTransportEventMap[K]) => void;

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
    await this.openSocket(false);
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.socket?.close();
    this.socket = null;
    this.setState('closed');
  }

  subscribe(cursor: SubscriptionCursor): void {
    const key = `${cursor.runId}:${cursor.channel}`;
    this.cursors.set(key, { ...cursor });
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.sendFrame('subscribe', {
        runId: cursor.runId,
        channel: cursor.channel,
        lastAppliedSequence: cursor.lastAppliedSequence,
      });
    }
  }

  private async openSocket(isReconnect: boolean): Promise<void> {
    this.setState(isReconnect ? 'reconnecting' : 'connecting');
    const WebSocketImpl = this.options.WebSocketImpl ?? WebSocket;
    const socket = new WebSocketImpl(this.options.url);
    this.socket = socket;

    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => {
        this.sendRaw(
          this.buildFrame('hello', {
            protocolVersion: PROTOCOL_VERSION_V1,
            authToken: this.options.token ?? null,
          }),
        );
      };

      socket.onmessage = (event) => {
        try {
          const frame = parseContract(websocketFrameSchema, JSON.parse(String(event.data)));
          this.handleFrame(frame, resolve);
        } catch (error) {
          reject(error instanceof Error ? error : new Error(String(error)));
        }
      };

      socket.onerror = () => {
        reject(new Error('WebSocket connection failed'));
      };

      socket.onclose = () => {
        this.socket = null;
        if (this.intentionalClose) {
          this.setState('closed');
          return;
        }
        this.scheduleReconnect();
      };
    });
  }

  private handleFrame(frame: WebSocketFrameV1, onConnected: () => void): void {
    switch (frame.messageType) {
      case 'hello_ack':
        this.reconnectAttempt = 0;
        this.setState('connected');
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
        this.emit('warning', { code: warningPayload.code, message: warningPayload.message });
        return;
      }
      default:
        return;
    }
  }

  private scheduleReconnect(): void {
    if (!this.options.autoReconnect || this.intentionalClose) {
      this.setState('disconnected');
      return;
    }
    this.reconnectAttempt += 1;
    const delay = computeReconnectDelayMs(this.reconnectAttempt, this.options.reconnectBackoff);
    this.setState('reconnecting');
    this.clearReconnectTimer();
    this.reconnectTimer = setTimeout(() => {
      void this.openSocket(true).catch(() => {
        this.scheduleReconnect();
      });
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
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
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(raw);
    }
  }

  private emit<K extends EventKey>(event: K, payload: RealtimeTransportEventMap[K]): void {
    for (const handler of this.handlers[event]) {
      handler(payload);
    }
  }
}
