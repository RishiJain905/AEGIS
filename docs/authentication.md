# Authentication and Authorization (Phase 30)

## Purpose

Phase 30 adds production-path **authentication** (who the operator is) and
**authorization** (what that operator may do). Enforcement is always server-side
at trusted HTTP and WebSocket boundaries. Frontend route guards and hidden
controls are usability only.

## Identity model

| Concept | Description |
|---------|-------------|
| User | Authored id `user:…` persisted in `auth_users` |
| External identity | OIDC issuer + subject mapped in `auth_external_identities` |
| Roles | `viewer`, `analyst`, `operator`, `scenario_author`, `admin` |
| Session | Opaque token (HttpOnly cookie) hashed in `auth_sessions` |
| Actor | `AuthenticatedActorV1` derived only from the session |

Client-supplied `X-Actor-Id`, `actorId`, roles, or bearer synthetic tokens are
**ignored** for identity. Approval `approverId` is always the authenticated
`userId`.

## Authentication flows

### Production — OIDC authorization-code + PKCE

1. `GET /api/v1/auth/login` redirects to the configured issuer
2. `GET /api/v1/auth/callback` validates state/PKCE, resolves linked user, creates session
3. Secure `aegis_session` HttpOnly cookie + readable `aegis_csrf` cookie are set
4. `POST /api/v1/auth/logout` revokes the session and clears cookies

### Development / test — explicit local login

- Enabled only when `AEGIS_DEV_AUTH_ENABLED=true` and `AEGIS_ENV` is not `production`
- `POST /api/v1/auth/dev/login` with `{ userId }` against seeded users
- **No password storage** in AEGIS
- Production startup **aborts** if dev auth or WS legacy dev auth is enabled

## Session lifecycle

- Cookie: `HttpOnly`, `SameSite=Lax`, `Secure` in production
- TTL: `AEGIS_SESSION_TTL_SECONDS` (default 8h)
- Login rotates session id (session fixation prevention)
- Logout / revocation sets `revoked_at`; subsequent HTTP and WS fail closed
- CSRF: synchronizer token via `aegis_csrf` cookie + `X-CSRF-Token` header on mutations
- Tokens never stored in `localStorage` or logged

## Role → permission matrix

| Permission | viewer | analyst | operator | scenario_author | admin |
|---|---|---|---|---|---|
| `runs:read` | Y | Y | Y | Y | Y |
| `runs:write` | | | Y | | Y |
| `investigation:read` | Y | Y | Y | Y | Y |
| `investigation:trigger` | | Y | Y | | Y |
| `approvals:decide` | | | Y | | Y |
| `replay:read` | Y | Y | Y | Y | Y |
| `replay:write` | | | Y | | Y |
| `reports:read` | Y | Y | Y | Y | Y |
| `reports:export` | | Y | Y | | Y |
| `reports:trigger` | | | Y | | Y |
| `scoring:read` | Y | Y | Y | Y | Y |
| `scoring:compute` | | Y | Y | | Y |
| `scoring:export` | | Y | Y | | Y |
| `scenarios:publish` | | | | Y | Y |
| `admin:manage` | | | | | Y |
| `ws:subscribe` | Y | Y | Y | Y | Y |

WARDEN policy metadata roles `incident_commander` / `security_lead` are satisfied
by any authenticated actor with `approvals:decide` (operator, admin). They are
not separate platform roles.

Optional `ResourceAccessGrant` rows further restrict run-scoped access when present.

## Enforcement points

| Surface | Mechanism |
|---------|-----------|
| HTTP | `require_actor` / `require_permission` FastAPI dependencies |
| Approvals | Session actor only; `approvals:decide` required |
| WebSocket | Session or short-lived `/api/v1/auth/ws-ticket`; `ws:subscribe` |
| Exports / scoring / replay writes | Permission-gated as above |
| Admin observability | `admin:manage` |

## CORS

`AEGIS_CORS_ALLOWED_ORIGINS` is an explicit allowlist. Wildcard origins with
credentials are rejected at production startup.

## Audit

`SecurityAuditEventV1` records login, logout, denial, role change, and privileged
actions without secrets, tokens, or cookies.

## Environment variables

See `.env.example` for `AEGIS_DEV_AUTH_*`, session cookie names, CSRF, CORS, and OIDC.

## Constraints for Phases 31–35

- Do not reintroduce client-trusted actor headers
- Do not enable dev auth in production images
- Preserve deny-by-default matrix and approval identity attribution
- Observability (31) and hardening (32) build on this IAM layer; do not replace it
