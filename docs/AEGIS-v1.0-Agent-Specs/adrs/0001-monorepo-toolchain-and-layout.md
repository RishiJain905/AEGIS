# ADR 0001: Monorepo Toolchain and Layout

## Status

Proposed — awaiting project-owner approval.

## Context

AEGIS v1.0 Phase 00 requires a reproducible mixed TypeScript/Python monorepo with pinned toolchains, CI, Docker Compose, and enforceable package boundaries. The repository started documentation-only.

Phase specifications reference project-root `architecture.md`, while the canonical architecture document currently lives at `docs/architecture.md`.

## Decision

1. **JavaScript toolchain:** pnpm workspaces (11.9.0) with Turborepo task orchestration and Node.js 22.x.
2. **Python toolchain:** uv workspace with Python 3.12, Ruff, mypy, pytest, and import-linter.
3. **Boundary enforcement:** dependency-cruiser (TypeScript) and import-linter (Python), both wired into `pnpm lint` and CI.
4. **Documentation layout:** `docs/architecture.md` remains canonical; root `architecture.md` is a symlink for agent ergonomics.
5. **Handoffs:** root `handoffs/` directory per phase execution protocol.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| npm / Yarn / Bun | Prohibited by `bestPractices.txt` and Phase 00 spec |
| Poetry / pip-tools | uv provides faster reproducible workspaces with lockfile parity to pnpm policy |
| Nx | Turborepo is sufficient for Phase 00 task graph with lower configuration surface |
| Moving all docs to repo root | Would break existing `docs/` structure; symlink preserves both |

## Consequences

- Contributors must install pnpm and uv.
- CI requires Corepack bootstrap for pnpm when not preinstalled.
- Any change to dependency direction or repository layout after Phase 00 requires migration notes and, when architectural, a new ADR.

## Security and reliability

- pnpm supply-chain controls are enabled in `.npmrc`.
- No architecture non-negotiable rules are changed.
- Placeholder service processes expose health only; no domain simulation or auth in Phase 00.

## Approval

- [ ] Project owner
