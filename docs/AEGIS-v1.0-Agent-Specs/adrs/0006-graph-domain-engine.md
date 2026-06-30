# ADR 0006: Graph Domain Engine (TypeScript + Graphology)

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 05 requires a renderer-independent graph domain engine with snapshot load, sequence/revision-aware delta application, consistency validation, pathfinding, neighborhoods, clustering metadata, and non-destructive filtering. `architecture.md` and `bestPractices.txt` designate Graphology as the in-browser operational graph model; Sigma.js (Phase 06) and Three.js (Phase 27) consume the same semantic state.

The repository already contains:

- Phase 01 canonical graph contracts (`GraphSnapshotV1`, `GraphDeltaV1`, etc.) in `contracts-ts` and `contracts-python`
- A Python workspace placeholder at `packages/graph-domain/` from Phase 00
- Phase 04 shell wiring that loads validated snapshots but defers rendering to Phase 06

Phase 05 must not leak Graphology types to consumers, must not depend on React or renderers, and must not duplicate Phase 01 wire contracts.

## Decision

1. **TypeScript-primary implementation:** Add `@aegis/graph-domain` as a TypeScript package inside `packages/graph-domain/`, implemented with Graphology and graphology algorithm libraries. This is the authoritative Phase 05 graph engine for browser-side analysis, replay, and future renderer adapters.

2. **Python stub retained:** `aegis_graph_domain` remains a minimal Python workspace member for import-boundary enforcement until a later phase requires server-side graph projection or analysis. Server-side algorithms are out of Phase 05 scope.

3. **Graphology is private:** Canonical-to-Graphology adapters live inside the package. Public exports are AEGIS-owned interfaces (`GraphStore`, `GraphDeltaApplyResult`, etc.) and canonical contract types re-exported from `@aegis/contracts-ts` where needed. Graphology `Graph` instances are not exported.

4. **Phase 05 interfaces are domain API, not wire contracts:** `GraphStore`, `NeighborhoodResult`, `IncidentSubgraphResult`, and `GraphConsistencyReport` are TypeScript domain interfaces owned by `@aegis/graph-domain`. They are not added to `contracts-ts` / `contracts-python` unless a future phase requires cross-language serialization.

5. **Dependencies:** `@aegis/graph-domain` depends only on `@aegis/contracts-ts`, `graphology`, `graphology-types`, `graphology-shortest-path`, and `graphology-components`. No React, Sigma.js, or Three.js.

## Alternatives considered

| Alternative                                 | Why not chosen                                                                                                                    |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Python-only graph-domain with networkx      | Graphology is the architecture-mandated browser model; duplicating algorithms in Python now adds drift without Phase 05 consumers |
| Graphology inside `apps/web`                | Violates package boundaries; Phase 06 and replay tooling need a shared domain package                                             |
| New cross-language GraphStore wire contract | Phase 05 engine is in-process; durable contracts remain Phase 01 graph payloads                                                   |
| Remove Python graph-domain package          | Breaks uv workspace layout and import-linter contracts established in Phase 00                                                    |

## Consequences

- Phase 06 Sigma renderer imports `@aegis/graph-domain` rather than owning graph state.
- Backend graph API phases project `GraphSnapshotV1` / `GraphDeltaV1` from PostgreSQL; they do not reimplement browser algorithms in Python for Phase 05.
- `pnpm test` includes graph-domain unit and performance tests.
- Graphology version upgrades require regression runs on deterministic path/neighborhood tests.

## Security and reliability

- Delta application is idempotent and fail-closed on sequence gaps and stale revisions.
- Canonical state is never deleted by filter operations (hidden ≠ deleted).
- No network, worker, or renderer dependencies in the domain package.

## Approval

- [ ] Project owner
