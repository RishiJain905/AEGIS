# ADR 0013: WebSocket Gateway

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 11 established PostgreSQL-authoritative event persistence, outbox relay, and Redis Streams delivery (`RealtimeMessageEnvelopeV1`). Phase 12 adds the browser/service-facing WebSocket gateway required by `architecture.md` and deferred explicitly in the Phase 11 handoff.

Requirements:

- Authenticate before subscription; authorize each run/channel server-side
- Versioned wire protocol with sequence cursors
- Reconnect via `lastAppliedSequence` with PostgreSQL gap repair
- Bounded per-connection queues and slow-client handling
- Cross-language contract tests

## Decision

1. **Protocol v1 contracts** in `aegis_contracts` / `@aegis/contracts-ts` as `WebSocketFrameV1` wrapping typed payloads. `event` messages embed existing `RealtimeMessageEnvelopeV1` without redefining domain event shape.

2. **Gateway package** at `apps/api/src/aegis_api/websocket/` with:
   - `WebSocketGatewayManager` for connection/subscription lifecycle
   - `GatewayStreamConsumer` using dedicated Redis group `aegis-ws-gateway`
   - `SubscriptionRecoveryService` reading `PostgresEventQueryRepository` for gaps/backfill
   - Hook-based `WebSocketAuthenticator` and `RunSubscriptionAuthorizer` (dev token in Phase 12; OIDC in Phase 30)

3. **Slow-client policy:** bounded `asyncio.Queue` per connection. On overflow, pause subscription and emit `snapshot_required` (`WS_QUEUE_OVERFLOW`) rather than unbounded buffering.

4. **TypeScript transport** in `@aegis/realtime-client` with jittered reconnect and cursor tracking. Not wired into command-centre shell until Phase 13.

5. **No competing store:** gateway does not persist events; it consumes Phase 11 streams and PostgreSQL history only.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| HTTP SSE only | Spec requires WebSocket gateway; bidirectional subscribe/heartbeat |
| Redis as reconnect source | Violates architecture; PG authoritative for gaps |
| OIDC in Phase 12 | Explicitly out of scope; hooks preserve protocol |
| Unbounded per-connection buffers | Violates acceptance criteria; risks OOM on slow clients |

## Consequences

- Phase 13 command-centre reducers consume `@aegis/realtime-client` without reimplementing transport.
- Duplicate Redis delivery is expected; clients dedupe by `eventId` / sequence.
- Production deployments must replace dev auth hooks before exposing the gateway publicly.
- Gateway metrics exposed via `GET /api/v1/realtime/streaming/status` → `gateway` field.

## Approval

- [ ] Project owner
