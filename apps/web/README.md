# web

Next.js command-centre web application.

## Ownership

- Application shell routes and layout (`features/shell/`)
- API client adapters (`lib/api/`)
- Ephemeral UI state (`stores/`)
- Graph rendering (Phase 06+)

## Allowed dependencies

- `@aegis/contracts-ts`, `@aegis/ui`, `@tanstack/react-query`, `zustand`, and approved frontend libraries.
- Must not import `apps/api` or Python packages directly.

## Development

```bash
pnpm --filter @aegis/web dev
```

Open `http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV` for the default fixture-backed command centre.

## Environment

| Variable                        | Default                 | Purpose                                                               |
| ------------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE` | `api`                   | `api` (default) or `fixture`; fixture is refused in production builds |
| `NEXT_PUBLIC_API_BASE_URL`      | `http://localhost:8000` | Production API base URL                                               |

## Tests

```bash
pnpm --filter @aegis/web test
pnpm --filter @aegis/web test:e2e
```

See [`docs/frontend/application-shell.md`](../../docs/frontend/application-shell.md) for shell architecture.
