# ADR 0010: Deterministic Simulation Core

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 09 introduces the deterministic simulation engine that owns scenario truth. Phase 01 provides durable entity and event contracts; Phase 02 provides PostgreSQL persistence; Phase 08 provides validated declarative scenario manifests via `aegis_scenario_sdk`.

Architecture rules require:

- Simulation is deterministic for fixed scenario version, seed, and configuration.
- Virtual clock and priority event queue ordered by `(sim_time, priority, tie_breaker)`.
- Run-local seeded randomness without global or wall-clock influence.
- Checkpoint support with crash recovery.
- Commands applied only after authorization.
- Normalized-event hash tests for reproducibility.

## Decision

1. **Ownership boundary:** Runtime engine logic lives in `packages/simulation-domain` (`aegis_simulation_domain`). Durable simulation wire contracts live in `aegis_contracts` / `@aegis/contracts-ts` per ADR 0002.

2. **Engine version:** `SIMULATION_ENGINE_VERSION = "0.0.0-phase09"` is recorded on runs, checkpoints, and normalized hashes. Incompatible engine versions fail closed on restore.

3. **Virtual clock:** `sim_time` advances only when events are processed or explicit advance commands run. `recorded_at` on emitted events derives from `RunConfigurationV1.recordedAtEpoch` plus sequence offset — never wall-clock time.

4. **Event queue:** Deterministic min-heap ordered by `(sim_time, priority, tie_breaker, event_id)`. Generator and scheduled manifest events share the same ordering semantics.

5. **Randomness:** Per-stream `random.Random` instances seeded via `SHA-256(run_seed:stream_name)`. Global `random` module state is prohibited in simulation paths.

6. **Runtime IDs:** Event and trace IDs derive deterministically from `(run_seed, sequence, type)` encoded as valid `evt_` / `trc_` prefixed identifiers. Golden hashes normalize `eventId`, `recordedAt`, and `traceId`.

7. **Checkpoints:** `SimulationCheckpointV1` stores engine version, SHA-256 checksum over canonical world-state snapshot JSON, and embedded `WorldStateSnapshotV1` including queue and RNG state. Persisted in PostgreSQL `simulation_checkpoints` table.

8. **Authorization:** State-changing `SimulationCommandV1` records require non-agent actors (`operator`, `system`) with authorization token present. Agent actors are rejected for direct mutations (proposals deferred to Phase 24).

9. **Scenario consumption:** Engine loads validated `ScenarioManifestV1` from `aegis_scenario_sdk` only. No platform hard-coding of Operation Silent Relay or other scenario content.

10. **No new delivery technology:** Event persistence uses existing `domain_events` + outbox pattern. Redis/WebSocket streaming remains Phase 11.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Put all contracts in simulation-domain | Durable cross-process contracts belong in contracts packages per ADR 0002 |
| Wall-clock `recorded_at` | Breaks golden replay determinism |
| Global Python `random` | Violates architecture determinism rule |
| In-memory-only checkpoints | Fails crash recovery acceptance criteria |
| Parse scenario YAML in simulation service | Duplicates Phase 08 SDK responsibility |

## Consequences

- Phase 10 authors scenario content declaratively; platform code stays scenario-agnostic.
- Phase 11 can relay persisted `domain_events` without re-deriving simulation truth.
- New simulation event types require `EventTypeRegistry` updates and golden fixture refresh.
- Checkpoint format changes require engine version bump and migration notes.

## Security and reliability

- Invalid, stale, duplicate, or unauthorized commands fail closed with structured errors.
- Checkpoint checksum mismatch rejects restore.
- Scenario plugins are allowlisted; no arbitrary code execution.

## Approval

- [ ] Project owner
