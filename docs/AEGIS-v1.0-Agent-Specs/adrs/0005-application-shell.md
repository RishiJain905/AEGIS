# ADR 0005: Application Shell

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 04 requires the navigable command-centre frame: routes, panel layout, typed client boundaries, TanStack Query for server state, Zustand for ephemeral UI state, and fixture-backed development mode. ADR 0004 deferred TanStack Query and Zustand to this phase.

## Decision

1. **Route conventions:** Next.js App Router routes under `apps/web/src/app/(shell)/` for scenarios, runs, incidents, replay, reports, and admin. Home redirects to `/scenarios`.
2. **Shell ownership:** Layout regions live in `apps/web/features/shell/` composing `@aegis/ui` primitives — no parallel component library.
3. **Server vs ephemeral state:** TanStack Query owns remote entities (scenarios, runs, incidents, alerts, graph snapshots). Zustand owns `OperatorWorkspaceState` and persisted `PanelPreferencesSchema` v1 only.
4. **API adapter boundary:** `AegisApiClient` interface in `apps/web/lib/api/types.ts`. `createFixtureProvider` and `createProductionClient` are separate adapters selected by `NEXT_PUBLIC_AEGIS_DATA_SOURCE`.
5. **Fixture development mode:** Default `fixture` adapter validates `apps/web/fixtures/shell-dataset.json` with Phase 01 `parseContract`. Profiles via `?profile=` exercise loading, empty, error, offline, reconnecting, read-only, and partial states.
6. **Web-local workspace contracts:** `OperatorWorkspaceState` and `PanelPreferencesSchema` remain in `apps/web/features/shell/contracts/` (UI-ephemeral, not durable cross-language contracts).
7. **Entity type exports:** Phase 01 `@aegis/contracts-ts` exports `ScenarioV1`, `RunV1`, `IncidentV1`, etc. for typed API client signatures (additive, no schema change).

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| Embed fixture JSON in components | Violates adapter boundary; blocks production swap |
| Store runs/incidents in Zustand | Violates architecture and bestPractices §11 |
| Put workspace contracts in `@aegis/contracts-ts` | Ephemeral UI state is not a durable cross-language contract |
| Skip production adapter | Phase 04 requires explicit adapter interface for future API integration |

## Consequences

- `apps/web` depends on `@tanstack/react-query` and `zustand`.
- Phase 06+ graph renderer mounts in `VisualizationSlot` without shell rework.
- Production API routes may 404 until backend phases land; fixture mode is the default dev path.
- Playwright e2e covers shell keyboard and responsive paths locally (not yet in CI).

## Security and reliability

- No architecture non-negotiable rules are changed.
- No authentication, offensive capability, or production remediation introduced.
- Fixture data uses synthetic IDs only.
- API errors map to `ApiClientError` with stable codes; route guards fail closed on 404.

## Approval

- [ ] Project owner
