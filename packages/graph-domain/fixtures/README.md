# Graph domain fixtures

Generated artifacts for local inspection or debugging. **Do not commit** `medium-graph-snapshot.json`.

Regenerate locally:

```bash
pnpm exec tsx packages/graph-domain/scripts/generate-medium-fixture.ts
```

Performance tests generate the medium snapshot in memory via `buildMediumGraphSnapshot()` in
`src/fixtures/medium-graph-snapshot.ts`.
