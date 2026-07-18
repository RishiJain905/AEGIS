# AEGIS Scenario Authoring

For the v1.0 authoring contract, use the [Scenario SDK reference](AEGIS-v1.0-Agent-Specs/scenario-and-simulation/08-scenario-sdk.md)
and the [scenario package validation guide](../packages/scenario-sdk/README.md). This
page is the concise operational pointer; the SDK contracts and schemas are authoritative.

> Phase 08 baseline — declarative scenario packages validated by `aegis-scenario-sdk`.

## Overview

Scenario content is **declarative**, **versioned**, and **untrusted**. Authors define YAML manifests describing topology, generators, hidden conditions, objectives, branches, and scoring. The Scenario SDK validates structure and semantics before publication. Phase 09 materializes validated manifests into the deterministic simulation runtime.

The SDK is independent of frontend rendering libraries (Sigma.js, Three.js, React).

## Package layout

```text
scenarios/<package-name>/
├── manifest.yaml              # ScenarioManifestV1 (required)
├── package.manifest.yaml      # ScenarioPackageManifestV1 (generated)
└── media/                     # Optional relative media files
```

Synthetic fixtures live under `scenarios/_fixtures/`. Production scenario content for Operation Silent Relay will expand in Phase 10.

## Schema versioning

| Contract | `schemaVersion` | Owner |
|----------|-----------------|-------|
| `ScenarioManifestV1` | `1` | `aegis-scenario-sdk` |
| `ScenarioPackageManifestV1` | `1` | `aegis-scenario-sdk` |

Rules:

- Additive optional fields within v1 remain compatible.
- Required-field or semantic changes require a version bump and migration notes.
- Platform compatibility uses `metadata.requiredPlatformVersion` compared against `WORKSPACE_VERSION` from `aegis_contracts`.

Regenerate JSON Schemas:

```bash
uv run python scripts/generate_scenario_schemas.py
```

Schemas are written to `schemas/scenario/v1/`.

## Identifier namespaces

### Graph entities (Phase 01 authored IDs)

Use canonical namespaces from `docs/contracts/versioning.md`:

- `asset:…`, `edge:…`, `business-unit:…` (zones/clusters)

### Manifest-local entities

Generators, hidden conditions, scheduled events, objectives, branches, and scoring criteria use manifest-local slugs:

```text
^[a-z][a-z0-9._-]{0,63}$
```

Examples: `gen-auth-logs`, `hidden-cause-01`, `evt-status-shift`.

## Manifest sections

| Section | Contract | Purpose |
|---------|----------|---------|
| `metadata` | `ScenarioMetadataV1` | Identity, semver version, platform requirement |
| `zones` | `ZoneDefinitionV1[]` | Security/logical zones mapped to graph clusters |
| `assets` | `AssetTemplateV1[]` | Authoring-time asset templates |
| `relationships` | `RelationshipTemplateV1[]` | Typed edges between assets |
| `generators` | `GeneratorDefinitionV1[]` | Telemetry generators with allowlisted plugins |
| `hiddenConditions` | `HiddenConditionDefinitionV1[]` | Hidden causes and reveal rules |
| `scheduledEvents` | `ScheduledEventDefinitionV1[]` | Authoring-time scheduled actions |
| `objectives` | `ObjectiveDefinitionV1[]` | Success/failure criteria |
| `branches` | `OutcomeBranchDefinitionV1[]` | Seed-weighted outcome branches |
| `scoring` | `ScoringDefinitionV1` | Weighted scoring criteria and rubric |
| `media` | `MediaReferenceV1[]` | Relative media paths only |

Reuse Phase 01 enums: `AssetType`, `RelationshipType`, `NodeStatus`.

## Behavior plugins (allowlist)

| Plugin ID | Config model |
|-----------|--------------|
| `telemetry.auth_attempt` | `failureRate`, `successRate` |
| `telemetry.api_request` | `requestsPerInterval`, `errorRate` |
| `telemetry.network_flow` | `bytesPerInterval`, `protocol` |
| `telemetry.health_check` | `healthyProbability` |
| `telemetry.database_query` | `queriesPerInterval`, `anomalyRate` |
| `telemetry.deployment_event` | `deploymentsPerInterval`, `failureRate` |
| `telemetry.process_activity` | `eventsPerInterval`, `suspiciousRate` |
| `telemetry.ai_inference` | `inferencesPerInterval`, `anomalyRate` |
| `effect.set_asset_status` | `status`, optional `assetId` |
| `effect.adjust_relationship_confidence` | `delta`, optional `edgeId` |
| `branch.seed_selector` | `branchGroup`, optional `candidateBranchIds` |

Unknown plugins fail validation with `UNKNOWN_PLUGIN`. Arbitrary code, prompts, and shell fields are rejected.

## Validation errors

| Code | Meaning |
|------|---------|
| `SCHEMA_VALIDATION_FAILED` | Pydantic structural validation failure |
| `DUPLICATE_ID` | Repeated identifier within the manifest |
| `DANGLING_REFERENCE` | Reference to unknown asset, zone, or local ID |
| `UNKNOWN_PLUGIN` | Plugin ID not in allowlist |
| `INVALID_PLUGIN_CONFIG` | Plugin config failed typed validation |
| `INVALID_BRANCH_WEIGHT` | Invalid or over-allocated branch weights |
| `PLATFORM_VERSION_INCOMPATIBLE` | Platform too old for scenario requirement |
| `CHECKSUM_MISMATCH` | Package file checksum does not match manifest |
| `UNSAFE_CONTENT` | Forbidden keys, URLs, or shell patterns |
| `PACKAGE_LAYOUT_INVALID` | Missing manifest or referenced file |
| `PUBLICATION_CONFLICT` | Published version already exists (immutable) |

## CLI commands

```bash
# Validate a package directory
uv run aegis-scenario validate scenarios/_fixtures/valid-minimal

# Print deterministic package checksum
uv run aegis-scenario hash scenarios/operation-silent-relay

# Generate package.manifest.yaml with file checksums
uv run aegis-scenario package scenarios/_fixtures/valid-minimal

# Publish immutable versioned artifact
uv run aegis-scenario publish scenarios/_fixtures/valid-minimal --output /tmp/published
```

## Checksum and immutability

- File checksums use `sha256:` prefixes over canonical bytes.
- Manifest documents are canonicalized to sorted JSON before hashing.
- Package checksum hashes sorted `path=checksum` lines.
- `publish` copies a validated package to `<output>/<scenarioId>/<version>/` and refuses overwrites.

## Constraints for Phases 09 and 10

Phase 09 (simulation core) must:

- Consume validated `ScenarioManifestV1` without redefining authoring shapes.
- Materialize `AssetTemplateV1` → runtime assets and `RelationshipTemplateV1` → graph edges.
- Interpret `ScheduledEventDefinitionV1` as authoring input for runtime `ScheduledEvent` (owned by Phase 09).
- Preserve deterministic ordering using `simTime`, `priority`, `tieBreaker`.

Phase 10 (Operation Silent Relay) must:

- Author full scenario content as declarative packages only.
- Not hard-code scenario values into platform code.
- Replace the Phase 08 skeleton under `scenarios/operation-silent-relay/` without changing SDK contracts.

## Migration guidance

When bumping `schemaVersion`:

1. Document breaking changes in the handoff and ADR.
2. Regenerate `schemas/scenario/v1/`.
3. Provide migration notes for published packages.
4. Never rewrite published scenario versions in place — publish a new version instead.
