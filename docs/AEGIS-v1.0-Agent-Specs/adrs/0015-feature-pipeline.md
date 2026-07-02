# ADR 0015: Feature Pipeline

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 14 must deliver versioned deterministic features with shared offline/online computation, provenance, and dataset exports. Inputs must come from authoritative PostgreSQL domain events, not renderer or WebSocket transport state. Hidden scenario truth must never enter inference features.

ADR 0014 directs Phase 14+ work to align with live command-centre semantics while PostgreSQL remains authoritative for history.

## Decision

1. **Contracts** live in `aegis_contracts.features` / `@aegis/contracts-ts` (`FeatureSchemaManifestV1`, `FeatureVectorV1`, `FeatureWindowV1`, `FeatureProvenanceV1`, `DatasetManifestV1`, `OnlineFeatureUpdateV1`) at schema version 1.

2. **Single transform engine** in `services/ml/src/aegis_ml/features/` serves offline dataset generation (`scripts/build_feature_dataset.py`) and online API computation (`POST /api/v1/features/compute`). No forked transformation logic.

3. **Window semantics:** tumbling windows keyed by `(runId, entityId, floor(simTime / 300s))`. Entity key is `payload.assetId` on telemetry events. Closure advances on simulation time; wall-clock time is never used.

4. **Late-event policy:** events targeting an already-closed window are rejected with `FEATURE_LATE_EVENT`. Events within the open window are included even if sequence arrives after prior events in the same window.

5. **Ordering:** ingest sorts by `sequence`; duplicate `eventId` values are rejected; out-of-order detection is exposed for diagnostics.

6. **Input guard:** only registered `telemetry.*` types are accepted. `sim.hidden_condition.*` and all other non-telemetry types are rejected. Malformed payloads missing `assetId` are rejected.

7. **Missing values:** rate features use sentinel `-1.0` when the denominator is zero. Categorical network protocol features use versioned one-hot mapping `{tcp, udp, __MISSING__}` with deterministic tie-breaking by bytes then lexical order.

8. **Datasets** are filesystem artifacts under `models/datasets/<run-id>/` with `DatasetManifestV1` checksums. No feature store or new PostgreSQL tables in Phase 14.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Separate offline and online transform modules | Risks silent drift; violates architecture parity requirement |
| Client-side feature computation | Violates authoritative PG rule; duplicates reducer state |
| Redis stream as feature input | PostgreSQL is authoritative; Redis is delivery only |
| Include hidden-condition events as features | Evaluation-only scenario truth must not leak into inference |

## Consequences

- Phases 15–17 consume `FEATURE_SCHEMA_VERSION` 1 vectors and must not reorder or rename features without a version bump.
- Changing window duration, late-event policy, or accepted event types requires ADR update and schema version bump.
- Online consumers should call the features API or shared Python module; they must not rebuild transforms independently.

## Approval

- [ ] Project owner
