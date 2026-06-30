# Phase 08 Handoff — Scenario SDK

## Status

`READY FOR VALIDATION`

## Implemented

Phase 08 deliverables per `docs/AEGIS-v1.0-Agent-Specs/scenario-and-simulation/08-scenario-sdk.md`:

- Declarative `ScenarioManifestV1` and `ScenarioPackageManifestV1` contracts with schema version 1
- Asset, relationship, zone, generator, hidden-condition, scheduled-event, objective, branch, scoring, and media templates
- Allowlisted behavior-plugin registry with typed configs (7 plugins)
- Safety validation for untrusted content (forbidden keys, unrestricted URLs, shell patterns)
- Semantic validation (duplicate IDs, dangling references, unknown plugins, branch weights, platform version)
- Deterministic package checksums and immutable publication workflow
- `aegis-scenario` CLI (`validate`, `hash`, `package`, `publish`)
- Synthetic fixtures under `scenarios/_fixtures/` and minimal `scenarios/operation-silent-relay/` skeleton
- JSON Schemas under `schemas/scenario/v1/`
- Authoring documentation and ADR 0009

## Files added

| Area | Key paths |
|------|-----------|
| SDK package | `packages/scenario-sdk/src/aegis_scenario_sdk/**` |
| Schemas | `schemas/scenario/v1/manifest.schema.json`, `package-manifest.schema.json` |
| Scripts | `scripts/aegis-scenario.py`, `scripts/generate_scenario_schemas.py` |
| Fixtures | `scenarios/_fixtures/*`, `scenarios/operation-silent-relay/manifest.yaml` |
| Tests | `tests/scenario_sdk/**` |
| Docs | `docs/scenario-authoring.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0009-scenario-sdk.md` |
| Screenshots | `apps/web/scripts/capture-scenario-sdk-demo.mjs` |

## Files modified

| File | Reason |
|------|--------|
| `packages/scenario-sdk/pyproject.toml` | Dependencies, CLI entry point |
| `packages/scenario-sdk/README.md` | Module map and commands |
| `packages/contracts-python/src/aegis_contracts/versioning.py` | `WORKSPACE_VERSION` → `0.0.0-phase08` |
| `packages/contracts-ts/src/versioning.ts` | Parity bump |
| `pyproject.toml` | `types-PyYAML` dev dependency for mypy |
| `uv.lock` | Lockfile refresh |
| `scenarios/operation-silent-relay/README.md` | Skeleton documentation |

## Files removed

| File | Reason |
|------|--------|
| None | — |

## Contracts introduced or changed

| Contract | Version | Description |
|----------|---------|-------------|
| `ScenarioManifestV1` | schema v1 | Declarative scenario topology and behavior manifest |
| `ScenarioPackageManifestV1` | schema v1 | Content-addressed package file manifest |
| `AssetTemplateV1` | schema v1 | Authoring-time asset definition |
| `RelationshipTemplateV1` | schema v1 | Authoring-time relationship definition |
| `GeneratorDefinitionV1` | schema v1 | Telemetry generator with allowlisted plugin |
| `HiddenConditionDefinitionV1` | schema v1 | Hidden cause authoring contract |
| `ScheduledEventDefinitionV1` | schema v1 | Authoring-time scheduled event (runtime owned by Phase 09) |
| `OutcomeBranchDefinitionV1` | schema v1 | Seed-weighted outcome branches |
| `ScoringDefinitionV1` | schema v1 | Weighted scoring criteria |
| `BehaviorPluginConfigV1` | schema v1 | Allowlisted plugin reference + typed config |
| `WORKSPACE_VERSION` | `0.0.0-phase08` | Workspace metadata parity bump |

Phase 01 durable wire contracts (`ScenarioV1`, `ScenarioVersionV1`, graph contracts) unchanged.

## Database migrations

None.

## Environment and configuration changes

None.

## Generated artifacts and fixtures

- `schemas/scenario/v1/*.schema.json` (regenerate: `uv run python scripts/generate_scenario_schemas.py`)
- Synthetic fixtures: `scenarios/_fixtures/valid-minimal`, `invalid-*`
- Minimal skeleton: `scenarios/operation-silent-relay/manifest.yaml`
- Screenshots: `/opt/cursor/artifacts/screenshots/08-scenario-validate-success.png`, `08-scenario-validate-failure.png`

## Tests added

| Test | Proves |
|------|--------|
| `tests/scenario_sdk/test_schema_models.py` | Valid fixtures parse; extra fields rejected |
| `tests/scenario_sdk/test_semantic_validation.py` | Invalid fixtures fail with expected error codes |
| `tests/scenario_sdk/test_safety_rules.py` | Unrestricted URLs rejected |
| `tests/scenario_sdk/test_plugin_registry.py` | Allowlist and typed plugin configs |
| `tests/scenario_sdk/test_checksum_determinism.py` | Deterministic package checksums |
| `tests/scenario_sdk/test_publication_immutability.py` | Re-publish conflict |
| `tests/scenario_sdk/test_platform_compatibility.py` | Platform version gating |
| `tests/scenario_sdk/test_cli.py` | CLI exit codes |
| `tests/scenario_sdk/test_acceptance_criteria.py` | Maps to spec §18 |
| `tests/scenario_sdk/test_package_boundaries.py` | No application dependencies |

**Totals:** 25 scenario SDK tests; full suite 159 passed, 11 skipped.

## Commands executed and results

Executed on branch `cursor/scenario-sdk-phase-08-fcfe`.

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `pnpm typecheck:py` | **PASS** (65 source files) |
| `uv run pytest -q` | **PASS** (159 passed, 11 skipped) |
| `uv run aegis-scenario validate scenarios/operation-silent-relay` | **PASS** |
| `uv run aegis-scenario validate scenarios/_fixtures/valid-minimal` | **PASS** |
| `uv run aegis-scenario validate scenarios/_fixtures/invalid-dangling-edge` | **FAIL** (exit 1, expected) |
| `pnpm check-contracts` | **PASS** |
| `uv run lint-imports` | **PASS** (4 contracts kept) |
| `pnpm --filter @aegis/web exec node scripts/capture-scenario-sdk-demo.mjs` | **PASS** |

## Architecture decisions and ADRs

- **Created:** [0009-scenario-sdk.md](../AEGIS-v1.0-Agent-Specs/adrs/0009-scenario-sdk.md) (Status: **Proposed**)
  - SDK ownership boundary for manifest contracts
  - Manifest-local ID strategy vs graph authored IDs
  - Content-addressed immutable publication
  - Behavior-plugin allowlist and untrusted-content safety rules

- **Unchanged:** ADRs 0001–0008, `architecture.md` non-negotiables

## Known limitations

- File-based publication only; database/API publication endpoints deferred
- No TypeScript mirror of manifest models (Python + JSON Schema sufficient for Phase 08)
- `operation-silent-relay` contains structural skeleton only; Phase 10 replaces content
- Plugin registry is minimal; Phase 09/10 may extend with ADR updates

## Deferred work

- Phase 09: `SimulationRuntime`, runtime `ScheduledEvent`, world state materialization
- Phase 10: Full Operation Silent Relay content, golden seeds, narrative
- Graphical scenario editor / marketplace
- Database-backed publication API

## Risks for dependent phases

- Phase 09 must consume validated `ScenarioManifestV1` from `aegis_scenario_sdk` without redefining shapes
- Phase 10 must author content as declarative packages; no platform hard-coding
- New behavior plugins require registry updates and tests
- Published scenario versions are immutable; content changes require new version strings

## Acceptance criteria evidence

| Criterion | Evidence |
|-----------|----------|
| Valid packages validate and hash deterministically | `test_checksum_determinism.py`, `test_acceptance_criteria.py`, CLI validate/hash, success screenshot |
| Unsafe/inconsistent packages fail with precise diagnostics | `test_semantic_validation.py`, `test_safety_rules.py`, failure screenshot (`DANGLING_REFERENCE`) |
| Published versions are immutable | `publication.py`, `test_publication_immutability.py`, `test_acceptance_criteria.py` |
| SDK independent of application internals | import-linter, `test_package_boundaries.py`, only `aegis-contracts` runtime dependency |

## Prohibited-shortcut confirmation

- No simulation engine (Phase 09) implemented
- No full Silent Relay narrative (Phase 10) in platform code
- No frontend rendering coupling
- No weakened validation or skipped tests
- All listed validation commands executed with recorded results
