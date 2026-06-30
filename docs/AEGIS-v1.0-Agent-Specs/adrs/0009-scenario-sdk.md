# ADR 0009: Scenario SDK

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 08 introduces declarative scenario authoring, validation, packaging, and publication. Phase 01 defines durable identity records (`ScenarioV1`, `ScenarioVersionV1`) but not topology, generators, objectives, or scoring manifests. Phase 09 requires validated scenario input without guessing semantics.

Architecture rules require:

- Published scenarios are immutable and content-addressed.
- Scenario content is untrusted and cannot execute arbitrary code.
- Simulation is deterministic for fixed version, seed, and configuration.
- Domain packages must not import application internals.

## Decision

1. **Ownership boundary:** Authoring contracts (`ScenarioManifestV1`, `ScenarioPackageManifestV1`, templates, plugins) live in `packages/scenario-sdk` (`aegis_scenario_sdk`). They are not duplicated in `aegis_contracts` unless a future phase promotes a subset to cross-process durable contracts.

2. **Identifier strategy:**
   - Graph-linked entities use Phase 01 authored IDs (`asset:`, `edge:`, `business-unit:`).
   - Manifest-internal entities (generators, conditions, events, branches, objectives, scoring criteria) use manifest-local slugs (`^[a-z][a-z0-9._-]{0,63}$`) scoped within a manifest.

3. **Validation pipeline:** Load → safety scan → Pydantic schema → semantic cross-reference checks → optional package checksum verification.

4. **Behavior plugins:** Only allowlisted plugin IDs with typed Pydantic configs. No arbitrary Python, prompts, or shell execution.

5. **Untrusted content:** Reject forbidden key names, unrestricted URL schemes, and shell-like patterns. Media paths must be relative without `..` traversal.

6. **Content addressing:** File and package checksums use `sha256:` prefixes. Manifest YAML is canonicalized to sorted JSON for hashing.

7. **Immutability:** `aegis-scenario publish` writes versioned artifacts and fails closed when a version directory already exists.

8. **Platform compatibility:** `metadata.requiredPlatformVersion` is compared against `WORKSPACE_VERSION` using PEP 440 semantics via the `packaging` library.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Put manifest models in `aegis_contracts` | Authoring contracts are SDK-owned; promoting to shared contracts deferred until cross-language consumers require it |
| Global authored IDs for generators/events | Would require expanding Phase 01 ID namespaces for every authoring entity |
| Execute scenario Python for behavior | Violates untrusted-content and determinism rules |
| Skip package checksums | Breaks immutability and publication guarantees |

## Consequences

- Phase 09 imports validated manifests from `aegis_scenario_sdk` rather than parsing YAML independently.
- Phase 10 authors content under `scenarios/` using SDK validation only.
- New behavior plugins require SDK registry updates and tests.
- JSON Schemas under `schemas/scenario/v1/` are generated from Pydantic and must be regenerated when models change.

## Security and reliability

- Fail closed on schema, safety, semantic, checksum, and publication conflicts.
- No secrets, prompts, or executable content in manifests.
- SDK depends only on `aegis-contracts` plus `pyyaml` and `packaging`.

## Approval

- [ ] Project owner
