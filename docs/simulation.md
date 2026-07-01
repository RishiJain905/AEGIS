# Phase 09 — Deterministic Simulation Core

## Purpose

The simulation runtime owns authoritative scenario truth for AEGIS v1.0. It consumes validated `ScenarioManifestV1` packages from the Scenario SDK and executes them deterministically using a virtual clock, seeded random streams, and a priority event queue.

## Lifecycle

| State | Description |
|-------|-------------|
| `created` | Run initialized; world materialized from manifest |
| `running` | Event queue processing active |
| `paused` | Queue frozen; state retained |
| `stopped` | Terminal state |

Commands: `start`, `step`, `advance`, `pause`, `resume`, `stop`, `checkpoint`, `restore`, `execute`.

## Virtual clock

- `sim_time` advances only when events are processed or `advance` is invoked.
- `recorded_at` on emitted events derives from `RunConfigurationV1.recordedAtEpoch` plus sequence offset.
- Wall-clock time is never used for domain ordering or outcomes.

## Event queue ordering

Events are ordered by `(sim_time, priority, tie_breaker, event_id)` using a deterministic min-heap. Generator ticks and manifest `scheduledEvents` share the same ordering semantics.

## Seeded randomness

Per-stream `random.Random` instances are keyed by `SHA-256(run_seed:stream_name)`. Global `random` state and wall-clock inputs are prohibited in simulation paths.

## Commands and authorization

`SimulationCommandV1` carries `actor`, `authorizationToken`, and `commandId` (idempotency key). Agent actors are rejected for direct state mutations. Idempotency records use scope `simulation-command`.

## Checkpoints

`SimulationCheckpointV1` stores engine version, SHA-256 checksum over canonical world-state JSON, and embedded `WorldStateSnapshotV1` (assets, relationships, generators, hidden conditions, queue, RNG state, sequence cursor).

Restore validates engine version and checksum before resuming execution.

## Normalized event hash

Golden replay hashes canonicalize event envelopes sorted by `sequence`, excluding `eventId`, `recordedAt`, and `traceId`. Hash format: `sha256:<hex>`.

## Engine version

`SIMULATION_ENGINE_VERSION = 0.0.0-phase09` — recorded on runs, checkpoints, and golden artifacts. Incompatible versions fail closed on restore.

## CLI

```bash
uv run aegis-simulator run --scenario scenarios/_fixtures/valid-minimal --seed 42 --steps 30
uv run aegis-simulator run --scenario scenarios/operation-silent-relay --seed 1000 --steps 300
uv run aegis-simulator determinism-check --scenario scenarios/operation-silent-relay --seed 1000 --steps 300
uv run aegis-simulator checkpoint-recovery-check --scenario scenarios/_fixtures/valid-minimal --seed 42 --steps 30 --checkpoint-at 10
uv run aegis-simulator seed-divergence-check --scenario scenarios/operation-silent-relay --seed-a 1000 --seed-b 1007 --steps 300
uv run aegis-simulator invalid-command-demo
```

Engine version: `0.0.0-phase10`. Branch-gated scheduled events and weighted `branch.seed_selector` use manifest `branchGroup` definitions. Hidden conditions emit `sim.hidden_condition.triggered` and `sim.hidden_condition.revealed` when thresholds or reveal timers are met.

## Constraints for later phases

- Phase 10: Author scenario content declaratively only; do not hard-code Silent Relay in platform code.
- Phase 11: Relay persisted `domain_events`; do not re-derive simulation truth from Redis or UI state.
- Phase 24: Agent state changes remain proposals routed through approval workflow.

## Package map

| Package | Responsibility |
|---------|----------------|
| `aegis_simulation_domain` | Virtual clock, queue, RNG, world state, handlers, runtime |
| `aegis_simulation` | Application service, CLI, persistence wiring |
| `aegis_contracts` | Durable simulation wire contracts |
