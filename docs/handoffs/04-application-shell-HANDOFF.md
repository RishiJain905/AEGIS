# Phase 04 Handoff — Application Shell

## Status

`READY FOR VALIDATION`

## Implemented

Phase 04 deliverables per `docs/AEGIS-v1.0-Agent-Specs/product-shell/04-application-shell.md`:

- Command-centre routes: scenarios, active run, incident, replay, reports, admin, not-found
- Shell regions: operations rail, visualization placeholder, inspector, timeline, status strip, command palette
- TanStack Query for server state; Zustand for ephemeral workspace and persisted panel preferences
- UI states: loading, empty, error, partial, offline, reconnecting, read-only, not-found
- Panel collapse/docking with localStorage persistence (`PanelPreferencesSchema` v1)
- Keyboard shortcuts: `Ctrl/Cmd+K` palette, `Ctrl/Cmd+B` rail, `Ctrl/Cmd+I` inspector; focus restoration on palette close
- `AegisApiClient` interface with separate fixture and production adapters
- Contract-validated fixture dataset (`apps/web/fixtures/shell-dataset.json`)
- Route guards with `notFound()` for invalid entity IDs
- Mobile drawer navigation below `lg` breakpoint
- Documentation and ADR 0005

## Files added

| Area               | Key paths                                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Shell feature      | `apps/web/features/shell/components/`, `contracts/`, `hooks/`                                                                                                |
| API layer          | `apps/web/lib/api/`, `apps/web/lib/providers.tsx`                                                                                                            |
| Store              | `apps/web/stores/workspace-ui-store.ts`                                                                                                                      |
| Fixtures           | `apps/web/fixtures/shell-dataset.json`                                                                                                                       |
| Routes             | `apps/web/src/app/(shell)/**`                                                                                                                                |
| Tests              | `apps/web/features/shell/contracts/contracts.test.ts`, `apps/web/lib/api/*.test.ts`, `apps/web/stores/workspace-ui-store.test.ts`, `tests/e2e/shell.spec.ts` |
| Docs               | `docs/frontend/application-shell.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0005-application-shell.md`                                                           |
| Screenshots script | `apps/web/scripts/capture-shell-screenshots.mjs` (not required at runtime)                                                                                   |

## Files modified

| File                                                          | Reason                                        |
| ------------------------------------------------------------- | --------------------------------------------- |
| `apps/web/package.json`                                       | Add TanStack Query, Zustand, Zod              |
| `apps/web/tsconfig.json`                                      | Path aliases for features/lib/stores/fixtures |
| `apps/web/vitest.config.ts`                                   | Test paths and aliases                        |
| `apps/web/src/app/layout.tsx`                                 | QueryClient provider                          |
| `apps/web/src/app/page.tsx`                                   | Redirect to `/scenarios`                      |
| `packages/contracts-ts/src/entities.ts`                       | Export entity V1 types for API client         |
| `packages/contracts-ts/src/versioning.ts`                     | Bump `WORKSPACE_VERSION`                      |
| `packages/contracts-python/src/aegis_contracts/versioning.py` | Bump `WORKSPACE_VERSION`                      |
| `.env.example`                                                | Web data-source env vars                      |
| `apps/web/README.md`                                          | Shell dev commands                            |
| `pnpm-lock.yaml`                                              | New dependencies                              |

## Files removed

| File | Reason |
| ---- | ------ |
| None | —      |

## Contracts introduced or changed

| Contract                                  | Version          | Description                                          |
| ----------------------------------------- | ---------------- | ---------------------------------------------------- |
| `OperatorWorkspaceState`                  | v1               | Ephemeral UI workspace state (web-local Zod)         |
| `PanelPreferencesSchema`                  | v1               | Persisted panel dock/collapse preferences            |
| `AegisApiClient`                          | v1               | Typed read-only API client interface                 |
| `FixtureProvider`                         | v1               | Fixture adapter implementing `AegisApiClient`        |
| `ScenarioV1`, `RunV1`, `IncidentV1`, etc. | additive exports | TypeScript entity exports from `@aegis/contracts-ts` |
| `WORKSPACE_VERSION`                       | `0.0.0-phase04`  | Workspace metadata                                   |

No durable cross-language schema changes.

## Database migrations

None.

## Environment and configuration changes

| Variable                        | Default                 | Purpose                              |
| ------------------------------- | ----------------------- | ------------------------------------ |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE` | `fixture`               | `fixture` or `api` adapter selection |
| `NEXT_PUBLIC_API_BASE_URL`      | `http://localhost:8000` | Production API base URL              |

## Generated artifacts and fixtures

- `apps/web/fixtures/shell-dataset.json` — validated shell fixture bundle with profiles for UI states
- Updated `pnpm-lock.yaml`

## Tests added

| Test                                         | Proves                                                                                        |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `features/shell/contracts/contracts.test.ts` | Workspace and panel schema validation                                                         |
| `lib/api/fixture-client.test.ts`             | Canonical fixture validation; profile behaviors                                               |
| `lib/api/query-keys.test.ts`                 | Stable TanStack Query keys                                                                    |
| `stores/workspace-ui-store.test.ts`          | Panel toggles and run-scoped reset                                                            |
| `tests/e2e/shell.spec.ts`                    | Desktop/narrow viewport navigation, keyboard palette, offline/empty/partial states, not-found |

## Commands executed and results

| Command                             | Result                                           |
| ----------------------------------- | ------------------------------------------------ |
| `pnpm format:check`                 | PASS                                             |
| `pnpm lint`                         | PASS (ESLint + dependency-cruiser: 0 violations) |
| `pnpm typecheck`                    | PASS                                             |
| `pnpm test`                         | PASS (97 tests: 60 contracts + 17 web + 20 ui)   |
| `pnpm build`                        | PASS                                             |
| `pnpm --filter @aegis/web test:e2e` | PASS (11 Playwright tests)                       |

Visual review command:

```bash
pnpm --filter @aegis/web dev
# http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
```

Screenshot capture (optional):

```bash
pnpm --filter @aegis/web start
pnpm --filter @aegis/web exec node scripts/capture-shell-screenshots.mjs
```

## Architecture decisions and ADRs

- **ADR 0005** (`docs/AEGIS-v1.0-Agent-Specs/adrs/0005-application-shell.md`): shell routes, TanStack Query/Zustand split, fixture vs API adapters, web-local workspace contracts.
- No changes to `architecture.md` non-negotiable rules.

## Known limitations

- Production API routes (`/api/v1/*`) are not implemented; `api` adapter will error until backend phases land.
- Graph visualization is a placeholder; Sigma.js deferred to Phase 06.
- Playwright e2e is not in CI (Phase 03 precedent); runs locally after `pnpm exec playwright install chromium`.
- Incident IDs containing `:` require URL encoding in links (`encodeURIComponent`).
- `next start` emits standalone output warning during e2e webServer (functional).

## Deferred work

- Sigma.js operational graph (Phase 06)
- WebSocket realtime (Phase 11–12)
- Authentication and authorization
- Replay engine (Phase 25–26)
- Reports/scoring (Phase 29)

## Risks for dependent phases

- Phase 06 mounts graph renderer inside `VisualizationSlot`; do not fork shell layout.
- Replace fixture adapter via `AegisApiClient` only; shell hooks consume `useApiClient()`.
- Preserve `OperatorWorkspaceState` and `PanelPreferencesSchema` v1 fields or version-bump with migration.
- URL-encode canonical IDs with reserved characters in route links.

## Acceptance criteria evidence

| Criterion                                               | Evidence                                                                                                                    |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| All product areas navigable through polished shell      | `tests/e2e/shell.spec.ts` navigates scenarios, run, incident, replay, reports, admin; screenshots in PR                     |
| Fixture data passes canonical runtime validation        | `lib/api/fixture-client.test.ts`; `validateShellDataset()` uses `parseContract` per entity                                  |
| Keyboard and viewport flows pass Playwright             | `tests/e2e/shell.spec.ts` keyboard palette + 768px mobile menu tests                                                        |
| Future integrations replace adapters not embedded fakes | `AegisApiClient` + `createApiClient()`; components use query hooks only; documented in `docs/frontend/application-shell.md` |

## Prohibited-shortcut confirmation

- No scaffolding-only shell; all routes render production-path components with state handling.
- No authoritative domain data in Zustand.
- No duplicate Phase 01 domain types; fixtures validated via `@aegis/contracts-ts`.
- No Phase 05+ features (graph renderer, auth, WebSocket) implemented.
- All listed validation commands executed with results recorded above.
- No tests deleted or weakened.
