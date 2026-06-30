# AEGIS Command

Interactive cyber-defence simulation and defensive-agent evaluation platform.

## Quick start

```bash
./scripts/bootstrap.sh
```

See [docs/engineering-standards.md](docs/engineering-standards.md) for the full command matrix, toolchain pins, and repository boundaries.

## Architecture

The implementation contract is [docs/architecture.md](docs/architecture.md) (also available at [architecture.md](architecture.md)).

Phase specifications live in [docs/AEGIS-v1.0-Agent-Specs/](docs/AEGIS-v1.0-Agent-Specs/).

## Phase 00 scope

This repository baseline includes:

- pnpm + uv monorepo skeleton matching the architecture tree
- ESLint, Prettier, TypeScript strict mode, Ruff, mypy, pytest
- Docker Compose for web, API, worker, simulator, PostgreSQL, Redis, and MinIO
- GitHub Actions CI with audits and boundary checks

Domain behavior begins in Phase 01+.
