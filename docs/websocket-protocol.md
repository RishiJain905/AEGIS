# AEGIS WebSocket Protocol v1

> Phase 12 — authenticated, sequence-aware live run delivery over WebSocket.

## Endpoint

```text
ws://{host}:{API_PORT}/ws/v1/realtime
```

Configurable via `AEGIS_WS_PATH` (default `/ws/v1/realtime`).

## Authority model

- **PostgreSQL** (`domain_events`) is authoritative for event history and gap repair.
- **Redis Streams** (`aegis:stream:domain-events`) provides at-least-once live fan-out.
- The gateway does **not** store durable events; it projects Phase 11 delivery envelopes to clients.

## Authentication (Phase 12 hooks)

Production OIDC is deferred to Phase 30. Phase 12 uses replaceable hooks:

| Hook | Phase 12 implementation |
|------|-------------------------|
| `WebSocketAuthenticator` | Dev bearer token in `hello` frame (`AEGIS_WS_DEV_AUTH_TOKEN`) |
| `RunSubscriptionAuthorizer` | Run must exist in PostgreSQL; optional principal run allow-list |

Fail closed when dev auth is disabled (`AEGIS_ENV=production` without explicit dev auth).

### Handshake

1. Client opens WebSocket.
2. Client sends `hello` with `protocolVersion: 1` and `authToken`.
3. Server responds `hello_ack` with `connectionId` and `principalId`, or `error` and closes on auth failure.

## Wire envelope

All frames use `WebSocketFrameV1`:

```json
{
  "schemaVersion": 1,
  "protocolVersion": 1,
  "messageType": "subscribe",
  "traceId": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
  "sentAt": "2026-06-30T12:00:00.000Z",
  "payload": {}
}
```

### Client → server

| messageType | Purpose |
|-------------|---------|
| `hello` | Protocol negotiation + auth token |
| `subscribe` | `{ runId, channel, lastAppliedSequence }` |
| `unsubscribe` | `{ runId, channel }` |
| `pong` | Heartbeat response |

### Server → client

| messageType | Purpose |
|-------------|---------|
| `hello_ack` | Connection established |
| `subscribed` | Subscription ack + `deliveryMode` |
| `event` | Wraps `RealtimeMessageEnvelopeV1` |
| `warning` | Duplicate suppressed, queue pressure |
| `error` | Structured `ApiErrorEnvelopeV1` |
| `snapshot_required` | Client must resync (gap, queue overflow) |
| `ping` | Heartbeat |
| `resync_complete` | Backfill delivery finished |

## Subscription lifecycle

1. Authenticated client sends `subscribe` with `lastAppliedSequence` cursor (0 = from start).
2. Server authorizes run/channel server-side.
3. Server loads missing events from PostgreSQL when `sequence > lastAppliedSequence`.
4. Server sends `subscribed` with `deliveryMode`: `stream`, `backfill`, or `snapshot_required`.
5. Server emits `event` frames in sequence order, then `resync_complete` when backfill finishes.
6. Live events arrive from the gateway Redis consumer group (`aegis-ws-gateway`).

## Cursor semantics

- `lastAppliedSequence` is the last **applied** domain event sequence for the run (not Redis offset).
- Reconnect: send `subscribe` with the last successfully processed sequence.
- Gaps in live delivery trigger PostgreSQL backfill before continuing.
- Large gaps (`> AEGIS_WS_SNAPSHOT_GAP_THRESHOLD`) emit `snapshot_required` (Phase 13 loads snapshots).

## Heartbeat

- Server sends `ping` every `AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS` (default 15s).
- Client must respond with `pong` within `AEGIS_WS_IDLE_TIMEOUT_SECONDS` (default 45s).
- Idle connections close with `WS_IDLE_TIMEOUT`.

## Message limits

- Maximum frame size: `AEGIS_WS_MAX_MESSAGE_BYTES` (default 65536).
- Oversized or invalid JSON/schema frames → `WS_INVALID_MESSAGE` or `WS_MESSAGE_TOO_LARGE`.

## Backpressure and slow clients

- Per-connection outbound queue bound: `AEGIS_WS_MAX_QUEUE_DEPTH` (default 256).
- On overflow: subscription paused, `snapshot_required` with `WS_QUEUE_OVERFLOW`, live fan-out stopped for that subscription.
- Prevents unbounded memory growth under slow consumers.

## Error codes

`WS_UNAUTHORIZED`, `WS_FORBIDDEN`, `WS_INVALID_MESSAGE`, `WS_MESSAGE_TOO_LARGE`, `WS_UNSUPPORTED_PROTOCOL`, `WS_UNKNOWN_RUN`, `WS_SEQUENCE_GAP`, `WS_QUEUE_OVERFLOW`, `WS_IDLE_TIMEOUT`, `WS_CONNECTION_LIMIT`

## TypeScript client

Package: `@aegis/realtime-client`

Authenticate with a short-lived WebSocket ticket from
`POST /api/v1/auth/ws-ticket` (session cookie + CSRF required). Do not embed
long-lived session secrets in the browser URL or localStorage.

```typescript
import { RealtimeTransport } from '@aegis/realtime-client';

const ticketRes = await fetch('/api/v1/auth/ws-ticket', {
  method: 'POST',
  credentials: 'include',
  headers: { 'X-CSRF-Token': csrfToken },
});
const { ticket } = await ticketRes.json();

const transport = new RealtimeTransport({
  url: 'ws://localhost:8000/ws/v1/realtime',
  token: ticket,
  autoReconnect: true,
});
await transport.connect();
transport.subscribe({ runId, channel: 'events', lastAppliedSequence: 0 });
```

`AEGIS_WS_DEV_AUTH_ENABLED` / `DevWebSocketAuthenticator` remain for narrow
local tests only and are rejected at startup when `AEGIS_ENV=production`.
See [`docs/authentication.md`](authentication.md).

## Diagnostic demo

`GET /realtime/websocket-demo` — browser-based gateway validation (not Phase 13 command-centre integration).

## Phase 13 constraints

Phase 13 must:

- Consume `@aegis/realtime-client` or equivalent protocol client
- Treat PostgreSQL/backfill as authoritative for reducers
- Not bypass server-side subscription authorization
- Not treat WebSocket connection state as durable truth

Phase 13 must **not** reimplement delivery or competing event stores.

## Related docs

- [realtime-streaming.md](./realtime-streaming.md) — Phase 11 outbox/Redis foundation
- ADR [0013-websocket-gateway.md](./AEGIS-v1.0-Agent-Specs/adrs/0013-websocket-gateway.md)
