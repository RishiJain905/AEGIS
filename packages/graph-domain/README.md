# graph-domain

Renderer-independent graph state, delta application, and algorithms for AEGIS v1.0.

## Packages

| Runtime    | Name                  | Status                                                                |
| ---------- | --------------------- | --------------------------------------------------------------------- |
| TypeScript | `@aegis/graph-domain` | **Phase 05 implementation** (Graphology-backed)                       |
| Python     | `aegis_graph_domain`  | Workspace stub for import boundaries; server-side projection deferred |

## TypeScript usage

```typescript
import { createGraphStore, GraphLayer } from '@aegis/graph-domain';

const store = createGraphStore();
store.loadSnapshot(snapshot);
store.applyDelta(delta);
const paths = store.queryPaths(pathQuery);
const view = store.applyFilters({ enabledLayers: [GraphLayer.INFRASTRUCTURE] });
```

## Dependencies

- `@aegis/contracts-ts` — canonical `GraphSnapshotV1`, `GraphDeltaV1`, path contracts
- `graphology` — private in-memory graph implementation (not exported)

Must not import apps, web, Sigma.js, Three.js, or React.

## Documentation

See [`docs/graph-domain.md`](../../docs/graph-domain.md) and ADR 0006.

## Validation

```bash
pnpm --filter @aegis/graph-domain typecheck
pnpm --filter @aegis/graph-domain test
```

## Performance fixtures

Medium-graph snapshots are generated in memory for tests (`src/fixtures/medium-graph-snapshot.ts`). Optional local JSON:

```bash
pnpm exec tsx packages/graph-domain/scripts/generate-medium-fixture.ts
```

See [`fixtures/README.md`](fixtures/README.md).
