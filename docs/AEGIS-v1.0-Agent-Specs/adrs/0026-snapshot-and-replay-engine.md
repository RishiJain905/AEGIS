# ADR 0026 — Snapshot and Replay Engine

## Status

Proposed

## Context

Architecture requires historical reconstruction by loading the closest prior snapshot and applying later authoritative events. Prior phases already provide:

- `domain_events` in PostgreSQL (source of truth)
- `GraphSnapshotV1` / `graph_snapshots` (live bootstrap / graph acceleration)
- `SimulationCheckpointV1` / `simulation_checkpoints` (engine crash recovery)
- Object-storage metadata via `stored_objects`

Phase 25 must add a multi-domain replay acceleration artifact without treating snapshots as authoritative history, without mutating live runs, and without regenerating LLM outputs.

## Decision

1. **Canonical contracts in shared packages** — `ReplaySnapshotV1`, `ReplayStateV1`, `ReplayCursorV1` / `ReplayCursorRangeV1`, `StateDiffV1`, `SnapshotManifestV1`, `ReplayProvenanceV1`, and `ReplayEquivalenceResultV1` live in `aegis_contracts` / `@aegis/contracts-ts` (schema v1). Spec path `packages/replay-contracts/**` maps to these packages per ADR 0002.

2. **Three snapshot kinds remain distinct**

   - `GraphSnapshotV1` — operational graph projection for live bootstrap/resync
   - `SimulationCheckpointV1` — simulation engine world-state crash recovery
   - `ReplaySnapshotV1` — multi-domain historical reconstruction acceleration

3. **PostgreSQL authority, object-storage archives** — `SnapshotManifestV1` rows in `replay_snapshot_manifests` store checksum, versions, event range, object key, and compatibility. Compressed gzip archives are stored in S3/MinIO behind `ObjectStoragePort` / `S3ObjectStorageAdapter`. Snapshots never replace `domain_events`.

4. **Deterministic projectors** — Server-side projectors reconstruct run, graph, incidents, evidence, risk, agents, proposals, approvals, actions, reports, and audit refs from events. Application is idempotent by `eventId`.

5. **Fail-closed integrity** — Checksum mismatch, missing archive, or incompatible projector/workspace/engine metadata marks the manifest incompatible and falls back to an earlier valid snapshot or full event replay from sequence 0.

6. **Live isolation** — Replay APIs and services are read-only over live run mutation paths. They may write snapshot artifacts only. Historical mode never implies control of the live simulation.

7. **Zero model calls in historical replay** — Persisted agent/generation artifacts are referenced; providers are not invoked.

8. **Equivalence** — Normalized `stateDigest` excludes provenance so event-only and snapshot+tail reconstructions of the same domain state compare equal.

## Consequences

- Phase 26 consumes `ReplayState` / `ReplayCursor` / `ReplayProvenance` / `StateDiff` without redefining them.
- Changing projector semantics or snapshot archive format requires projector/workspace version bumps and migration notes.
- Corrupt or tampered archives degrade safely without blocking reconstruction from PostgreSQL events.
- Redis absence does not block replay; events are loaded from PostgreSQL.

## References

- `docs/AEGIS-v1.0-Agent-Specs/human-control-and-replay/25-snapshot-and-replay-engine.md`
- `docs/architecture.md` §11, §17
- ADR 0002 — Shared contract versioning
- ADR 0003 — PostgreSQL persistence and outbox
- ADR 0010 — Deterministic simulation core
- ADR 0012 — Event persistence and streaming
- ADR 0014 — Live command-centre integration
- `docs/replay-engine.md`
