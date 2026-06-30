# Phase 01 Handoff — Shared Contracts

## Status

`READY FOR VALIDATION`

This handoff is factual evidence for an independent validation agent. The implementation agent does not self-approve.

## Implemented

Phase 01 deliverables per `docs/AEGIS-v1.0-Agent-Specs/foundation/01-shared-contracts.md`:

- Canonical Pydantic contracts in `aegis_contracts` (primitives, errors, events, graph, entities, api, versioning, parsing, fixtures)
- Equivalent Zod contracts in `@aegis/contracts-ts` with `FIXTURE_SCHEMA_MAP` for cross-language tests
- `DomainEventEnvelopeV1` and `EventTypeRegistry` with known v1 event types
- Graph contracts: `GraphNodeV1`, `GraphEdgeV1`, `GraphClusterV1`, `GraphSnapshotV1`, `GraphDeltaV1`, `GraphPathQueryV1`, `GraphPathResultV1`
- Base entity records: scenario, scenario version, run, alert, incident, evidence, hypothesis, agent session, action proposal, approval, executed action, model manifest, model score
- API contracts: `ApiErrorEnvelopeV1`, `CursorPaginationV1`, `IdempotencyMetadataV1`, `ProtocolVersion`
- 23 valid + 4 invalid golden JSON fixtures, 23 generated JSON Schemas, compatibility manifest
- Cross-language round-trip and failure-path tests (Python pytest + TypeScript Vitest)
- `scripts/check_contract_compatibility.py`, `scripts/generate_contract_schemas.py`, root `pnpm check-contracts`
- `docs/contracts/versioning.md`, ADR `0002-shared-contract-versioning-and-identifiers.md`
- Preserved Phase 00 env contracts (`AegisSettings`, `aegisEnvironmentSchema`) and tooling

## Files added

| Area                 | Key paths                                                                                                                                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python contracts     | `packages/contracts-python/src/aegis_contracts/{primitives,errors,events,graph,entities,api,versioning,parsing,fixtures}.py`, `py.typed`                                                                                            |
| TypeScript contracts | `packages/contracts-ts/src/{primitives,errors,events,graph,entities,api,versioning,parsing}.ts`                                                                                                                                     |
| Fixtures             | `tests/contract/fixtures/valid/*.json` (23), `tests/contract/fixtures/invalid/*.json` (4), `tests/contract/fixtures/schemas/*.schema.json` (23), `compatibility-manifest.json`                                                      |
| Tests                | `tests/contract/test_cross_language_*.py`, `test_schema_versions.py`, `test_contract_dependencies.py`, `tests/unit/test_contract_primitives.py`, `packages/contracts-ts/tests/cross-language-*.test.ts`, `invalid-fixtures.test.ts` |
| Scripts              | `scripts/check_contract_compatibility.py`, `scripts/generate_contract_schemas.py`                                                                                                                                                   |
| Docs                 | `docs/contracts/versioning.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0002-shared-contract-versioning-and-identifiers.md`                                                                                                               |

## Files modified

| File                                                        | Reason                                                          |
| ----------------------------------------------------------- | --------------------------------------------------------------- |
| `packages/contracts-python/src/aegis_contracts/__init__.py` | Export domain contracts                                         |
| `packages/contracts-ts/src/index.ts`                        | Export domain contracts + fixture map; bump `WORKSPACE_VERSION` |
| `apps/api/src/aegis_api/main.py`                            | Import `WORKSPACE_VERSION` from `aegis_contracts`               |
| `package.json`                                              | Add `check-contracts`; include `docs/contracts` in format paths |
| `.dependency-cruiser.cjs`                                   | Allow intra-package module imports in `contracts-ts`            |
| `docs/engineering-standards.md`                             | Document contract commands and versioning                       |
| Package READMEs                                             | Module maps and consumer guidance                               |

## Files removed

None.

## Contracts introduced or changed

| Contract                                                           | Version         | Description                                     |
| ------------------------------------------------------------------ | --------------- | ----------------------------------------------- |
| `WORKSPACE_VERSION`                                                | `0.0.0-phase01` | Workspace metadata constant (Python + TS)       |
| `DomainEventEnvelopeV1`                                            | schema v1       | Append-only event envelope per architecture §7  |
| `EventTypeRegistry`                                                | v1              | Known event types and payload schema versions   |
| `GraphNodeV1` / `GraphEdgeV1` / `GraphSnapshotV1` / `GraphDeltaV1` | schema v1       | Operational graph contracts per architecture §9 |
| `GraphPathQueryV1` / `GraphPathResultV1`                           | schema v1       | Path analysis request/result                    |
| `ApiErrorEnvelopeV1`                                               | schema v1       | Standard API error shape                        |
| `CursorPaginationV1` / `IdempotencyMetadataV1`                     | schema v1       | API protocol helpers                            |
| Base entity records (`ScenarioV1`, `RunV1`, `IncidentV1`, etc.)    | schema v1       | Core domain IDs and lifecycle fields            |
| `ContractValidationError` / error codes                            | v1              | Structured contract boundary failures           |
| `compatibility-manifest.json`                                      | manifest v1     | SHA-256 hashes for breaking-change detection    |

Phase 00 env contracts (`AegisSettings`, `aegisEnvironmentSchema`) unchanged.

## Database migrations

None (Phase 02).

## Environment and configuration changes

None beyond existing `.env.example` from Phase 00.

## Generated artifacts and fixtures

- 23 JSON Schemas under `tests/contract/fixtures/schemas/` (regenerate: `uv run python scripts/generate_contract_schemas.py`)
- `tests/contract/fixtures/compatibility-manifest.json` (46 artifact hashes)
- Golden fixtures use synthetic IDs only (no Operation Silent Relay platform values)

## Tests added

| Test                                                           | Proves                                                              |
| -------------------------------------------------------------- | ------------------------------------------------------------------- |
| `tests/contract/test_cross_language_fixtures.py`               | All valid golden fixtures parse in Python                           |
| `tests/contract/test_cross_language_roundtrip.py`              | Python serialize/deserialize preserves semantics                    |
| `tests/contract/test_cross_language_invalid.py`                | Unknown schema versions and invalid IDs fail with structured errors |
| `tests/contract/test_schema_versions.py`                       | Supported/unsupported schema version matrix                         |
| `tests/contract/test_contract_dependencies.py`                 | Contract package has no apps/services imports                       |
| `tests/unit/test_contract_primitives.py`                       | ID and timestamp validator edge cases                               |
| `packages/contracts-ts/tests/cross-language-fixtures.test.ts`  | All valid fixtures parse in TypeScript                              |
| `packages/contracts-ts/tests/cross-language-roundtrip.test.ts` | TS round-trip semantic preservation                                 |
| `packages/contracts-ts/tests/invalid-fixtures.test.ts`         | TS failure paths match Python behavior                              |

**Totals:** 122 pytest tests passed; 58 Vitest tests passed (56 contracts-ts + 1 ui + 1 web).

## Commands executed and results

Executed on branch `cursor/phase-01-shared-contracts-f86e`.

| Command                | Result                                                                  |
| ---------------------- | ----------------------------------------------------------------------- |
| `pnpm format:check`    | **PASS**                                                                |
| `pnpm lint`            | **PASS** (ESLint + dependency-cruiser: 0 violations)                    |
| `pnpm typecheck`       | **PASS** (3/3 packages)                                                 |
| `pnpm test`            | **PASS** (58 Vitest tests)                                              |
| `pnpm build`           | **PASS** (Next.js production build)                                     |
| `pnpm check-contracts` | **PASS**                                                                |
| `uv run ruff check .`  | **PASS**                                                                |
| `pnpm typecheck:py`    | **PASS** (canonical equivalent of `uv run mypy apps services packages`) |
| `uv run pytest -q`     | **PASS** (122 passed)                                                   |

## Architecture decisions and ADRs

- **Created:** [0002-shared-contract-versioning-and-identifiers.md](../AEGIS-v1.0-Agent-Specs/adrs/0002-shared-contract-versioning-and-identifiers.md) (Status: **Proposed**)

  - Pydantic-canonical JSON Schema generation
  - Authored/runtime ID validation rules
  - Compatibility manifest hash policy
  - Structured contract error catalog

- **Unchanged:** ADR 0001 (monorepo toolchain and layout)

## Known limitations

- `EventTypeRegistry` lists representative v1 types; scenario-specific payload schemas expand in later phases
- Entity records are base contracts only (no ORM, persistence, or route handlers)
- `uv run mypy apps services packages` reports duplicate-module path errors; use `pnpm typecheck:py` per Phase 00 convention
- Compatibility manifest must be regenerated when fixture file bytes change (including Prettier reformatting)

## Deferred work

- Phase 02: PostgreSQL models, Alembic migrations, repositories
- Phase 03+: UI design system, graph engine, simulation, agents, ML
- ORM mappings, route handlers, Graphology/Sigma adapters
- Realtime WebSocket envelopes (build on event contracts in Phase 11–12)

## Risks for dependent phases

- Import domain types only from `aegis_contracts` / `@aegis/contracts-ts`; never duplicate shapes
- Changing v1 required fields requires schema version bump, manifest update, and migration notes per `docs/contracts/versioning.md`
- New ID namespaces require ADR or versioning doc update
- Run `pnpm check-contracts` whenever shared fixtures or schemas change

## Acceptance criteria evidence

| Criterion                                                                   | Evidence                                                                                                          |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Python and TypeScript round-trip golden fixtures without semantic loss      | `test_cross_language_roundtrip.py`, `cross-language-roundtrip.test.ts` (23 fixtures each)                         |
| Contracts have no UI, ORM, provider, or renderer dependencies               | `pyproject.toml` / `package.json` deps; `test_contract_dependencies.py`; dependency-cruiser + import-linter clean |
| Breaking changes detected automatically                                     | `scripts/check_contract_compatibility.py`, `compatibility-manifest.json`, `pnpm check-contracts`                  |
| Unknown schema versions and invalid identifiers fail with structured errors | `test_cross_language_invalid.py`, `invalid-fixtures.test.ts`, `test_schema_versions.py`                           |

## Prohibited-shortcut confirmation

- No ORM models, route handlers, business services, or renderer-specific fields were added
- No Silent Relay scenario values in platform code; fixtures use synthetic IDs
- No duplicate domain types in feature packages
- No tests deleted or weakened
- All listed validation commands were executed with results recorded above
- Implementation agent does not self-approve
