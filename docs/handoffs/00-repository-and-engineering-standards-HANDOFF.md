# Phase 00 Handoff — Repository and Engineering Standards

## Status

`READY FOR VALIDATION`

This handoff is factual evidence for an independent validation agent. The implementation agent does not self-approve.

## Implemented

Phase 00 deliverables per `docs/AEGIS-v1.0-Agent-Specs/foundation/00-repository-and-engineering-standards.md`:

- Full architecture-defined repository tree with package ownership README stubs
- pnpm 11.9.0 workspace with Turborepo, strict TypeScript, ESLint, Prettier, and supply-chain settings in `pnpm-workspace.yaml`
- uv Python 3.12 workspace with Ruff, mypy, pytest, import-linter, and pip-audit
- Root orchestration scripts: `bootstrap`, `format:check`, `lint`, `typecheck`, `typecheck:py`, `test`, `build`, `clean`, `boundaries`, `validate-env`
- Minimal runnable shells: `apps/web` (Next.js), `apps/api` (FastAPI `/health`, `/ready`), worker and simulator processes
- Shared environment validation in `@aegis/contracts-ts` (Zod) and `aegis_contracts` (Pydantic Settings)
- dependency-cruiser + import-linter boundary enforcement with negative regression fixtures
- Docker Compose for web, api, worker, simulator, PostgreSQL, Redis, MinIO
- GitHub Actions CI: static JS/Py checks, boundaries, compose, gitleaks
- `docs/engineering-standards.md`, updated `docs/architecture.md` status, root `architecture.md` symlink, `ARCH-Explained.md` stub

## Files added

| Area          | Key paths                                                                                                                                                                                                                                                         |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Monorepo root | `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `pyproject.toml`, `uv.lock`, `turbo.json`, `tsconfig.base.json`, `.prettierrc.json`, `eslint.config.mjs`, `.dependency-cruiser.cjs`, `.env.example`, `docker-compose.yml`, `.dockerignore`, `.gitignore` |
| Apps          | `apps/web/`, `apps/api/`                                                                                                                                                                                                                                          |
| Services      | `services/{simulation,incidents,agents,ml,workers}/`                                                                                                                                                                                                              |
| Packages      | `packages/{contracts-ts,contracts-python,ui,scenario-sdk,graph-domain,policy,observability}/`                                                                                                                                                                     |
| Tests         | `tests/contract/`, `tests/unit/`, `tests/fixtures/boundary-violation/`                                                                                                                                                                                            |
| Infra/CI      | `.github/workflows/ci.yml`, Dockerfiles under apps and services                                                                                                                                                                                                   |
| Docs          | `docs/engineering-standards.md`, `ARCH-Explained.md`, `docs/handoffs/`, ADR `0001-monorepo-toolchain-and-layout.md`                                                                                                                                               |
| Scripts       | `scripts/bootstrap.sh`, `scripts/validate_env.py`                                                                                                                                                                                                                 |

## Files modified

| File                      | Reason                                      |
| ------------------------- | ------------------------------------------- |
| `README.md`               | Bootstrap workflow and project overview     |
| `docs/architecture.md`    | Status label updated to AEGIS v1.0 baseline |
| `docs/handoffs/README.md` | Phase handoff index and naming convention   |
| `architecture.md`         | Symlink to `docs/architecture.md`           |

## Files removed

None.

## Contracts introduced or changed

| Contract                 | Version         | Description                                                                        |
| ------------------------ | --------------- | ---------------------------------------------------------------------------------- |
| `WORKSPACE_VERSION`      | `0.0.0-phase00` | Shared workspace metadata constant (TS)                                            |
| `aegisEnvironmentSchema` | v1 (implicit)   | Zod schema for required environment variables                                      |
| `AegisSettings`          | v1 (implicit)   | Pydantic Settings mirror of env contract                                           |
| CI task names            | stable          | `format:check`, `lint`, `typecheck`, `typecheck:py`, `test`, `build`, `boundaries` |
| Boundary rules           | v1              | dependency-cruiser + import-linter layer contracts                                 |

No domain event, graph, or API domain contracts were introduced (Phase 01 scope).

## Database migrations

None (Phase 02).

## Environment and configuration changes

- `.env.example` documents all required variables (no secrets)
- `pnpm-workspace.yaml` holds supply-chain and `allowBuilds` policy (pnpm 11+)
- `.npmrc` retains `engine-strict=true` only
- Bootstrap copies `.env.example` → `.env` when missing

## Generated artifacts and fixtures

- `pnpm-lock.yaml`, `uv.lock` (committed, reproducible)
- `tests/fixtures/boundary-violation/` deliberate TS/Python boundary violations for regression tests
- Next.js build output under `apps/web/.next/` (gitignored)

## Tests added

| Test                                       | Proves                                              |
| ------------------------------------------ | --------------------------------------------------- |
| `packages/contracts-ts/tests/env.test.ts`  | Zod env validation success/failure paths            |
| `packages/ui/tests/ui.test.ts`             | Workspace package wiring                            |
| `apps/web/tests/web.test.ts`               | Web → UI → contracts dependency chain               |
| `tests/unit/test_settings.py`              | Pydantic settings validation and failure paths      |
| `tests/unit/test_api_health.py`            | FastAPI `/health` and `/ready` endpoints            |
| `tests/contract/test_repository_layout.py` | Required directory tree and `.env.example` hygiene  |
| `tests/contract/test_boundary_rules.py`    | Boundary tools pass on repo; negative fixtures fail |

**Totals:** 37 pytest tests passed; 6 Vitest tests passed.

## Commands executed and results

Executed on branch `cursor/phase-00-foundation-20c4` at commit pending push.

| Command                                 | Result                                                                                                                                                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm install --frozen-lockfile`        | **PASS** (pnpm 11.9.0; lockfile passes supply-chain policies)                                                                                                                                                                   |
| `uv sync --frozen --all-packages`       | **PASS** (canonical equivalent of `uv sync --frozen` for uv workspace members)                                                                                                                                                  |
| `pnpm format:check`                     | **PASS**                                                                                                                                                                                                                        |
| `pnpm lint`                             | **PASS** (ESLint + dependency-cruiser: 0 violations)                                                                                                                                                                            |
| `pnpm typecheck`                        | **PASS** (3/3 packages)                                                                                                                                                                                                         |
| `pnpm test`                             | **PASS** (6 Vitest tests)                                                                                                                                                                                                       |
| `pnpm build`                            | **PASS** (Next.js production build)                                                                                                                                                                                             |
| `uv run ruff check .`                   | **PASS**                                                                                                                                                                                                                        |
| `pnpm typecheck:py`                     | **PASS** (mypy over installed workspace packages; canonical equivalent of `uv run mypy apps services packages`)                                                                                                                 |
| `uv run pytest -q`                      | **PASS** (37 passed)                                                                                                                                                                                                            |
| `docker compose config`                 | **PASS**                                                                                                                                                                                                                        |
| `docker compose build`                  | **FAIL** in this cloud VM — Docker daemon cannot start (`iptables`/`nf_tables` NAT chain unsupported). Compose file and Dockerfiles are present; **CI `compose` job is expected to validate builds on GitHub Actions runners.** |
| `pnpm audit --audit-level high`         | **PASS** (exit 0; 2 moderate remain, triaged)                                                                                                                                                                                   |
| `pnpm audit signatures`                 | **PASS** (350 packages verified; requires pnpm ≥ 11.1)                                                                                                                                                                          |
| `uv run pip-audit`                      | **PASS** (no known vulnerabilities in PyPI deps; workspace packages skipped as local)                                                                                                                                           |
| `pnpm validate-env`                     | **PASS**                                                                                                                                                                                                                        |
| `uv run python scripts/validate_env.py` | **PASS**                                                                                                                                                                                                                        |
| `./scripts/bootstrap.sh`                | **PASS** (full bootstrap workflow)                                                                                                                                                                                              |

## Architecture decisions and ADRs

- **Created:** [0001-monorepo-toolchain-and-layout.md](../docs/AEGIS-v1.0-Agent-Specs/adrs/0001-monorepo-toolchain-and-layout.md) (Status: **Proposed**)
  - pnpm 11.9.0 (required for `pnpm audit signatures` per `bestPractices.txt`)
  - uv + Python 3.12 workspace
  - Turborepo task graph
  - dependency-cruiser + import-linter boundaries
  - Canonical docs in `docs/` with root `architecture.md` symlink

No other ADRs were modified or superseded.

## Known limitations

- Docker image builds were not executed successfully in the implementation environment (daemon/network constraints).
- `ARCH-Explained.md` is a stub; full narrative deferred.
- Python mypy uses installed package modules (`pnpm typecheck:py`) to avoid duplicate module path errors with `mypy apps services packages`.
- Placeholder service processes expose health only; no domain simulation, auth, or persistence logic.
- 2 moderate npm advisories remain (below `--audit-level high` threshold).

## Deferred work

- Phase 01: shared domain contracts
- Phase 02: database models and Alembic migrations
- Phase 03+: UI design system, graph, simulation, agents, ML
- Kubernetes and production cloud deployment
- Trivy container scanning (CI compose job builds images; add scan when daemon available)
- Full `ARCH-Explained.md` narrative

## Risks for dependent phases

- Phase 01 must extend `contracts-ts` and `contracts-python` without duplicating types elsewhere.
- pnpm 11 requires settings in `pnpm-workspace.yaml`; do not move supply-chain settings back to `.npmrc` alone.
- `minimumReleaseAge` may block freshly published packages; pin versions or document narrow exceptions.
- Independent validator should re-run `docker compose build` on a host with a working Docker daemon.

## Acceptance criteria evidence

| Criterion                                                | Evidence                                                                                                                |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Clean checkout bootstraps via one documented workflow    | `./scripts/bootstrap.sh` documented in `README.md` and `docs/engineering-standards.md`; bootstrap executed successfully |
| Frozen installs and root quality commands pass           | All JS/Py static commands above pass except `docker compose build` (environment limitation)                             |
| Repository boundaries match architecture; cycles fail CI | `pnpm boundaries` clean; `uv run lint-imports` clean; negative fixtures fail in `tests/contract/test_boundary_rules.py` |
| No secrets or machine-local paths committed              | `.gitignore` excludes `.env`; `.env.example` only; gitleaks CI job configured                                           |

## Prohibited-shortcut confirmation

- No domain logic, scenario content, auth, or ML was implemented.
- No npm/yarn/bun usage.
- No stubs with TODO-only production paths; health endpoints and env validation are real.
- No tests were deleted or weakened to pass.
- Validation results are recorded honestly; `docker compose build` failure is not concealed.
