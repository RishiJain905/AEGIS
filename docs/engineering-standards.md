# AEGIS Engineering Standards

> Phase 00 baseline — mandatory for all contributors and coding agents.

## Bootstrap workflow

From a clean checkout:

```bash
./scripts/bootstrap.sh
```

This command:

1. Copies `.env.example` to `.env` when `.env` is missing
2. Runs `pnpm install --frozen-lockfile`
3. Runs `uv sync --frozen --all-packages`
4. Validates environment variables (TypeScript + Python)

## Runtime pins

| Tool    | Version                                         |
| ------- | ----------------------------------------------- |
| Node.js | 22.x (see `.node-version`)                      |
| pnpm    | 11.9.0 (see `packageManager` in `package.json`) |
| Python  | 3.12 (see `.python-version`)                    |
| uv      | latest compatible with lockfile                 |

CI installs pnpm via Corepack without assuming it is preinstalled globally.

## Package manager policy

**pnpm is the only JavaScript/TypeScript package manager.** Do not use npm, npx, Yarn, or Bun for package management.

## Root commands

| Command                              | Purpose                                    |
| ------------------------------------ | ------------------------------------------ |
| `pnpm bootstrap`                     | One-shot local setup                       |
| `pnpm format:check`                  | Prettier check (implementation paths only) |
| `pnpm lint`                          | ESLint + TypeScript boundary checks        |
| `pnpm boundaries`                    | dependency-cruiser layer rules             |
| `pnpm typecheck`                     | TypeScript strict check                    |
| `pnpm test`                          | Workspace unit tests                       |
| `pnpm build`                         | Production builds                          |
| `uv run ruff check .`                | Python lint                                |
| `uv run mypy apps services packages` | Python type check                          |
| `uv run pytest -q`                   | Python tests                               |
| `uv run lint-imports`                | Python import boundaries                   |
| `docker compose config`              | Validate Compose file                      |
| `docker compose build`               | Build local service images                 |

## Repository boundaries

Dependency direction matches `architecture.md`:

- `apps/web` → TypeScript packages only
- `apps/api` → Python packages and services (not web)
- `services/*` → domain packages
- Domain packages must not import apps or services
- `scenarios/*` use scenario SDK only (Phase 08+)

Violations fail CI via dependency-cruiser and import-linter.

## pnpm supply-chain controls

Configured in `pnpm-workspace.yaml` (pnpm 11+). Legacy `.npmrc` retains engine strictness only.

- Minimum release age (1440 minutes)
- Block exotic subdependencies
- Strict peer dependencies and engine checks
- Curated `onlyBuiltDependencies` allowlist in `package.json`

## Environment variables

All variables are documented in `.env.example`. Secrets must never be committed.

Shared validation:

- TypeScript: `@aegis/contracts-ts` (Zod)
- Python: `aegis_contracts` (Pydantic Settings)

## ADR and handoff conventions

- ADRs live in `docs/AEGIS-v1.0-Agent-Specs/adrs/`
- Phase handoffs live in `handoffs/`
- Canonical architecture contract: `docs/architecture.md` (also linked from root `architecture.md`)

## Deferred to later phases

Domain contracts, database migrations, auth, simulation, graph, agents, ML, and production cloud deployment are out of Phase 00 scope.
