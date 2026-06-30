# scenario-sdk

Declarative scenario authoring, validation, packaging, and publication for AEGIS v1.0.

## Ownership

Phase 08 owns scenario manifest contracts, validation, checksums, behavior-plugin allowlists, and the `aegis-scenario` CLI. Phase 01 owns durable identity records (`ScenarioV1`, `ScenarioVersionV1`).

## Module map

| Module           | Responsibility                                               |
| ---------------- | ------------------------------------------------------------ |
| `contracts/`     | `ScenarioManifestV1`, `ScenarioPackageManifestV1`, templates |
| `validation/`    | Safety, semantic, and pipeline validation                    |
| `plugins/`       | Allowlisted behavior plugins and typed configs               |
| `packaging/`     | Checksums and package manifest construction                  |
| `publication.py` | Immutable publish workflow                                   |
| `cli.py`         | `aegis-scenario` commands                                    |

## Commands

```bash
uv run aegis-scenario validate <package-dir>
uv run aegis-scenario hash <package-dir>
uv run aegis-scenario package <package-dir>
uv run aegis-scenario publish <package-dir> --output <dir>
```

## Documentation

- Authoring guide: [`docs/scenario-authoring.md`](../../docs/scenario-authoring.md)
- ADR: [`docs/AEGIS-v1.0-Agent-Specs/adrs/0009-scenario-sdk.md`](../../docs/AEGIS-v1.0-Agent-Specs/adrs/0009-scenario-sdk.md)

## Dependencies

- `aegis-contracts` (Phase 01 primitives, graph enums, versioning)
- `pyyaml`, `packaging`

Must not import `apps/*` or `services/*`.
