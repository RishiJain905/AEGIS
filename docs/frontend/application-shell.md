# AEGIS Application Shell

> Phase 04 baseline — command-centre routes, layout regions, data adapters, and UI-state contracts.

## Ownership

| Area                     | Path                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------- |
| Shell layout and regions | [`apps/web/features/shell/`](../apps/web/features/shell/)                           |
| API client adapters      | [`apps/web/lib/api/`](../apps/web/lib/api/)                                         |
| Ephemeral UI store       | [`apps/web/stores/workspace-ui-store.ts`](../apps/web/stores/workspace-ui-store.ts) |
| Fixture dataset          | [`apps/web/fixtures/shell-dataset.json`](../apps/web/fixtures/shell-dataset.json)   |
| E2E tests                | [`tests/e2e/shell.spec.ts`](../tests/e2e/shell.spec.ts)                             |

## Routes

| Route                     | Purpose                                     |
| ------------------------- | ------------------------------------------- |
| `/`                       | Redirects to `/scenarios`                   |
| `/scenarios`              | Scenario selection                          |
| `/runs/[runId]`           | Primary command-centre shell                |
| `/incidents/[incidentId]` | Incident-focused shell                      |
| `/replay/[runId]`         | Replay placeholder                          |
| `/reports`                | Reports placeholder                         |
| `/admin`                  | Administration placeholder                  |
| `/design-system`          | Phase 03 design-system showcase (preserved) |

## Shell regions

```text
┌────────────┬──────────────────────────────────────────┬────────────┐
│ Operations │ Status strip + connection banner         │ Inspector  │
│ rail       ├──────────────────────────────────────────┤ panel      │
│            │ Visualization slot (graph placeholder)   │            │
│            ├──────────────────────────────────────────┤            │
│            │ Timeline area                            │            │
└────────────┴──────────────────────────────────────────┴────────────┘
```

- **Operations rail:** route navigation, collapse toggle, mobile drawer below `lg`
- **Status strip:** connection state, read-only badge, run ID, simulation time
- **Visualization slot:** validated graph snapshot metadata; Sigma.js deferred to Phase 06
- **Inspector panel:** dockable/collapsible; incidents and alerts from TanStack Query
- **Timeline area:** fixture-backed `TimelineMark` list with ephemeral cursor in Zustand
- **Command palette:** `⌘K` / `Ctrl+K` searchable navigation and panel toggles

## State ownership

| Data                                                              | Owner                                         |
| ----------------------------------------------------------------- | --------------------------------------------- |
| Scenarios, runs, incidents, alerts, graph snapshots               | TanStack Query via `AegisApiClient`           |
| Selected entity, palette open, timeline cursor, presentation mode | Zustand `OperatorWorkspaceState`              |
| Panel dock/collapse preferences                                   | Zustand persist (`PanelPreferencesSchema` v1) |
| Connection status                                                 | TanStack Query (`getConnectionStatus`)        |

Authoritative domain status is never stored only in Zustand.

## Data adapters

Set `NEXT_PUBLIC_AEGIS_DATA_SOURCE`:

- `fixture` (default) — loads [`shell-dataset.json`](../apps/web/fixtures/shell-dataset.json), validates every entity with Phase 01 contracts
- `api` — fetches from `NEXT_PUBLIC_API_BASE_URL` (`/api/v1/*`)

Fixture profiles via `?profile=` query param: `default`, `loading`, `empty`, `error`, `offline`, `reconnecting`, `readonly`, `partial`.

Future phases replace adapters by implementing `AegisApiClient`; shell components consume hooks only.

## UI states

| State        | Trigger                                     | Component                  |
| ------------ | ------------------------------------------- | -------------------------- |
| Loading      | Query pending / `?profile=loading`          | `LoadingState`             |
| Empty        | Zero scenarios                              | `EmptyState`               |
| Error        | Query failure / `?profile=error`            | `ErrorState`               |
| Partial      | Missing graph snapshot / `?profile=partial` | `Alert` + empty viz        |
| Offline      | `?profile=offline`                          | `DisconnectedState` banner |
| Reconnecting | `?profile=reconnecting`                     | Status strip + banner      |
| Read-only    | `?profile=readonly`                         | Status strip badge         |
| Not found    | Invalid run/incident ID                     | `not-found.tsx`            |

## Commands

```bash
pnpm --filter @aegis/web dev          # Visual review at http://localhost:3000
pnpm --filter @aegis/web test         # Shell unit tests
pnpm --filter @aegis/web test:e2e     # Playwright shell path
```

Default visual-review URL:

```text
http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
```

## Deferred to later phases

- Sigma.js graph renderer (Phase 06)
- WebSocket realtime stream (Phase 11–12)
- Authentication and authorization
- Replay engine (Phase 25–26)
- Reports and scoring (Phase 29)
