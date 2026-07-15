# ADR 0031: Authentication and Authorization

## Status

Accepted (Phase 30 implementation)

## Context

Phases 12 and 24 shipped replaceable identity hooks:

- WebSocket `DevWebSocketAuthenticator` with `AEGIS_WS_DEV_AUTH_TOKEN`
- Approval workflow `synthetic-operator-token` and client-supplied `X-Actor-Id` / `actorId`

Architecture §18 requires production OIDC and five platform roles. Phase 30 must
replace those hooks without changing the approval state machine (ADR 0025) or
WebSocket wire protocol (ADR 0013).

## Decision

1. **Provider-neutral OIDC authorization-code + PKCE** behind an adapter protocol,
   with secure HttpOnly SameSite session cookies after callback.
2. **Server-side sessions in PostgreSQL** (`auth_sessions`) storing only token
   hashes; raw tokens never logged or placed in localStorage.
3. **Explicit development auth** (`POST /api/v1/auth/dev/login`) against seeded
   users with **no password storage**. Production startup fails closed when
   `AEGIS_DEV_AUTH_ENABLED` or legacy WS dev auth is enabled.
4. **Deny-by-default permission matrix** in `aegis_policy.authz` for roles
   `viewer`, `analyst`, `operator`, `scenario_author`, `admin`.
5. **WARDEN approver role aliases** (`incident_commander`, `security_lead`) map to
   platform `approvals:decide`; they are not new platform roles.
6. **Approval identity** is derived only from `AuthenticatedActorV1`; client actor
   fields and synthetic bearer tokens are ignored.
7. **WebSocket** authenticates via session cookie token or short-lived WS ticket
   from `/api/v1/auth/ws-ticket`, enforcing `ws:subscribe` and optional resource grants.
8. **CSRF** synchronizer token for cookie-authenticated mutations; **CORS**
   explicit origin allowlist with credentials (no wildcard).

## Consequences

- All protected HTTP routers and WS subscriptions require authenticated sessions.
- Existing approval/event/replay contracts remain unchanged aside from actor source.
- Phases 31–35 must preserve server-side enforcement and must not reintroduce
  client-trusted identity headers.

## References

- `docs/AEGIS-v1.0-Agent-Specs/production-readiness/30-authentication-and-authorization.md`
- ADR 0013 — WebSocket Gateway
- ADR 0025 — Approval Workflow
- `docs/authentication.md`
