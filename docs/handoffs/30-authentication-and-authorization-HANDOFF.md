# Phase 30 Handoff — Authentication and Authorization

## Status

`READY FOR VALIDATION`

## Implemented behavior (Sections 7 and 18)

| Spec item                                         | Implementation                                                                                                 |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Provider-neutral OIDC + server sessions           | `apps/api/src/aegis_api/auth/oidc.py`, session cookies via `auth/router.py` + `auth/service.py`                |
| Secure cookies + CSRF + CORS allowlist            | HttpOnly session cookie; CSRF header required on mutations; `CORSMiddleware` from `AEGIS_CORS_ALLOWED_ORIGINS` |
| Dev auth (no passwords) fail-closed in production | `POST /api/v1/auth/dev/login`; `assert_secure_auth_configuration` aborts production startup                    |
| Role/permission matrix deny-by-default            | `packages/policy/src/aegis_policy/authz/matrix.py`                                                             |
| HTTP enforcement                                  | `require_actor` / `require_permission` on protected routers in `main.py` + stronger mutation deps              |
| Approval identity from session only               | `ApprovalWorkflowService._resolve_authenticated_actor`; client `actorId` / `X-Actor-Id` ignored                |
| WebSocket session/ticket auth                     | `SessionWebSocketAuthenticator`; `POST /api/v1/auth/ws-ticket`                                                 |
| Security audit events                             | `SecurityAuditEventV1` persisted via auth repository                                                           |
| Frontend session UX                               | `apps/web/features/auth/**`, `/sign-in`, AuthGate, identity badge, role-gated approval affordances             |
| **AC1** Unauthorized cannot read/mutate           | Security + integration auth tests; unauthenticated `401` on protected HTTP                                     |
| **AC2** HTTP and WS auth consistent               | Same session/ticket + `ws:subscribe`; gateway integration tests                                                |
| **AC3** Approval identity cannot be forged        | Viewer `403` with forged headers; operator session-derived `user:…`                                            |
| **AC4** Session expiry/revocation tested          | Logout revokes session; subsequent calls fail closed                                                           |

**Explicitly not implemented:** Phase 31 observability, Phase 32 hardening beyond Phase 30 auth controls, SCIM, password DB, billing, frontend-only auth.

## Files added

| Path                                            | Reason                                |
| ----------------------------------------------- | ------------------------------------- |
| `packages/contracts-*/src/auth.*`               | Auth contracts                        |
| `packages/policy/src/aegis_policy/authz/**`     | Permission matrix + decisions         |
| `migrations/versions/013_auth_identity.py`      | Users/sessions/roles/grants/audit     |
| `packages/persistence/.../repositories/auth.py` | Auth persistence                      |
| `apps/api/src/aegis_api/auth/**`                | OIDC, sessions, deps, routes, startup |
| `apps/web/features/auth/**`                     | Login/session/logout UI               |
| `apps/web/src/app/(public)/sign-in/**`          | Sign-in route                         |
| `tests/security/auth/**`                        | Unit/security matrix, CSRF, startup   |
| `tests/integration/auth/**` + `auth_helpers.py` | Postgres auth flows                   |
| `tests/e2e/auth.spec.ts`                        | Playwright auth path                  |
| `docs/authentication.md`                        | Operator/architecture auth docs       |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0031-*.md`    | ADR                                   |
| `docs/handoffs/evidence/phase-30/**`            | Screenshots + recording               |
| `apps/web/scripts/capture-auth-demo.mjs`        | Visual evidence harness               |

## Files modified

| Path                                                                | Reason                                     |
| ------------------------------------------------------------------- | ------------------------------------------ |
| `apps/api/.../main.py`                                              | CORS, auth router, permission mounts       |
| Protected routers (runs/investigation/reports/scoring/replay/…)     | Auth deps                                  |
| `apps/api/.../approvals/**`                                         | Session actor only                         |
| `apps/api/.../websocket/auth.py`                                    | Session/ticket authenticator               |
| Frontend API fetch / live-run / approval controls                   | Credentials + role UX                      |
| `docs/approval-workflow.md`, `docs/websocket-protocol.md`, ADR 0025 | Remove synthetic-token production guidance |
| Settings / `.env.example` / workspace version `0.0.0-phase30`       | Auth env + contracts                       |

## Files removed

None.

## Contracts introduced or changed

Durable cross-language (schemaVersion 1):

- `AuthenticatedActorV1`, `RoleContractV1` / `PlatformRoleV1`, `PermissionV1`
- `ResourceAccessGrantV1`, `AuthorizationDecisionV1`, `SessionInfoV1`
- `SecurityAuditEventV1`, `AuthSessionResponseV1`, `DevLoginRequestV1`

`WORKSPACE_VERSION` = `0.0.0-phase30`.

## Migrations, env, fixtures, commands

- Migration `013_auth_identity`
- Env: `AEGIS_DEV_AUTH_ENABLED`, `AEGIS_SESSION_*`, `AEGIS_CSRF_*`, `AEGIS_CORS_ALLOWED_ORIGINS`, `AEGIS_OIDC_*`, `AEGIS_WEB_BASE_URL`
- Seeded dev users (viewer/analyst/operator/scenario_author/admin) on non-production startup
- Contract fixtures under `tests/contract/fixtures/`
- Evidence under `docs/handoffs/evidence/phase-30/`

## Tests added

| Test                                              | Proves                                             |
| ------------------------------------------------- | -------------------------------------------------- |
| `tests/security/auth/test_authz_matrix.py`        | Deny-by-default matrix + WARDEN alias mapping      |
| `tests/security/auth/test_http_auth_guards.py`    | Unauth / forbidden / CSRF / role boundaries        |
| `tests/security/auth/test_session_and_startup.py` | Session lifecycle + production fail-closed         |
| `tests/integration/auth/test_auth_flow.py`        | Login/logout/revocation/WS ticket against Postgres |
| `tests/integration/{run-api,websocket}` updates   | Credentialed HTTP/WS                               |
| `tests/e2e/auth.spec.ts`                          | Sign-in, identity, viewer, logout                  |

## Validation commands and results

| Command                                                                                                                                                                                           | Result                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `pnpm format:check`                                                                                                                                                                               | PASS                                                                                              |
| `pnpm lint`                                                                                                                                                                                       | PASS                                                                                              |
| `pnpm typecheck`                                                                                                                                                                                  | PASS                                                                                              |
| `pnpm test`                                                                                                                                                                                       | PASS                                                                                              |
| `pnpm build`                                                                                                                                                                                      | PASS (includes `/sign-in`)                                                                        |
| `pnpm check-contracts`                                                                                                                                                                            | PASS                                                                                              |
| `uv run ruff check .`                                                                                                                                                                             | PASS                                                                                              |
| `pnpm typecheck:py`                                                                                                                                                                               | PASS (364 source files)                                                                           |
| `uv run lint-imports`                                                                                                                                                                             | PASS (4 contracts kept)                                                                           |
| `uv run pytest -q` (without `AEGIS_INTEGRATION_POSTGRES`)                                                                                                                                         | PASS — 921 passed, 8 skipped                                                                      |
| `AEGIS_INTEGRATION_POSTGRES=1 uv run alembic upgrade head`                                                                                                                                        | PASS                                                                                              |
| `AEGIS_INTEGRATION_POSTGRES=1 uv run pytest tests/integration/auth tests/integration/websocket tests/integration/run-api tests/security/auth -q`                                                  | PASS                                                                                              |
| Full `tests/integration`                                                                                                                                                                          | 51 passed; 2 pre-existing agent flow failures (`evidence:ev_001` grounding) unrelated to Phase 30 |
| `pnpm --filter @aegis/web test:e2e -- tests/e2e/auth.spec.ts`                                                                                                                                     | PASS — 4 passed                                                                                   |
| Note: `uv run mypy apps services packages` (path mode) hits a pre-existing dual-module error in `services/agents/.../factory.py`; package mode `pnpm typecheck:py` is the project gate and passes |

### Demo / visual evidence

```bash
# API + web (fixture UI, live auth API)
uv run uvicorn aegis_api.main:create_app --factory --host 0.0.0.0 --port 8000
cd apps/web && NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 pnpm dev
SCREENSHOT_BASE_URL=http://127.0.0.1:3000 node apps/web/scripts/capture-auth-demo.mjs
```

## Architecture decisions and ADR references

- ADR 0031 — Authentication and Authorization (new)
- ADR 0025 updated — session-derived approval identity
- ADR 0013 / Phase 12 hooks preserved at protocol boundary; production path uses sessions/tickets

## Known limitations and deferred work

- OIDC provider adapter is production path; local/dev uses explicit seeded identities (no password store).
- CSRF token is returned in session JSON for cross-origin web→API (cookie readable only on API origin).
- Optional resource grants are implemented in persistence/authz; most routes rely on role permissions today.
- Phase 31 observability and Phase 32 broader hardening remain deferred.

## Risks and instructions for dependent phases

- Never reintroduce client-trusted `X-Actor-Id` / synthetic approval tokens on production paths.
- Keep production startup fail-closed for `AEGIS_DEV_AUTH_ENABLED` and `AEGIS_WS_DEV_AUTH_ENABLED`.
- Frontend role hiding is usability only; always enforce on server.
- Preserve approval state machine and WebSocket wire protocol when extending auth.

## Evidence for every acceptance criterion

| AC  | Evidence                                                                                                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC1 | Unauthenticated HTTP `401`; screenshots `30-unauthenticated-sign-in.png`, `30-access-denied-redirect-sign-in.png`; security tests                                                   |
| AC2 | WS ticket + `ws:subscribe`; `tests/integration/websocket/test_gateway.py`; live-run uses `/auth/ws-ticket`                                                                          |
| AC3 | Viewer approve with forged `X-Actor-Id` → `403 FORBIDDEN` (`approvals:decide`); screenshots `30-viewer-approval-controls-hidden.png` vs `30-operator-approval-controls-enabled.png` |
| AC4 | Logout revocation integration test; screenshots `30-logout-unauthenticated.png`; recording `30-auth-login-logout.webm`                                                              |

Additional visuals: operator identity (`30-operator-identity-and-roles.png`), viewer role (`30-viewer-authenticated-read-only.png`), protected after-action/replay, narrow layout.

## Confirmation: no prohibited shortcut used

Production enforcement is server-side (HTTP deps, approval service, WS authenticator, startup guards). No password DB, no localStorage tokens, no frontend-only auth. Synthetic identity hooks replaced without changing approval/WS state machines. Existing tests were updated to authenticate rather than loosened. Phase 31/32 scope was not absorbed.
