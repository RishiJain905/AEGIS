# Snapshot and Replay Engine (Phase 25)

Backend reconstruction of authoritative application state from PostgreSQL
`domain_events`, optional `ReplaySnapshot` archives, and deterministic projectors.

This is **not** a video recorder, frontend history buffer, or Phase 26 scrubbing UI.

## Authority

| Store                                        | Role                                             |
| -------------------------------------------- | ------------------------------------------------ |
| PostgreSQL `domain_events`                   | Authoritative history                            |
| `replay_snapshot_manifests` + MinIO archives | Acceleration / recovery artifacts                |
| Redis                                        | Delivery only; rebuildable from PostgreSQL       |
| Browser / live reducer                       | Live projection only; never historical authority |

## Contracts

- `ReplaySnapshotV1`
- `ReplayStateV1`
- `ReplayCursorV1` / `ReplayCursorRangeV1`
- `StateDiffV1`
- `SnapshotManifestV1`
- `ReplayProvenanceV1`
- `ReplayEquivalenceResultV1`

Runtime snapshot ids use prefix `rps_`.

## Snapshot schema and cadence

Manifest fields include: schema/scenario/engine/projector/workspace versions,
event range, checksum (`sha256:`), compression (`gzip`), object key, state digest,
trigger reason, retention class, compatibility flag.

Default cadence: every **50** sequences (`AEGIS_SNAPSHOT_INTERVAL`), plus explicit
API/CLI create and terminal run completion via the snapshot worker.

Object key pattern:

```text
snapshots/{runId}/{sequence}/{snapshotId}.json.gz
```

## Reconstruction algorithm

1. Resolve target cursor (`sequence` primary; optional `simTime` / `incidentId`).
2. Load nearest prior compatible snapshot with `sequence <= target`.
3. Verify archive checksum and compatibility; on failure mark incompatible and fall back.
4. Load events `(snapshot.sequence, target]` from PostgreSQL ordered by sequence.
5. Detect sequence gaps; fail closed with `REPLAY_SEQUENCE_GAP`.
6. Apply events through idempotent projectors (`eventId`).
7. Return `ReplayState` + `ReplayProvenance` (always).

## Cursor semantics

- Ordering is by authoritative event `sequence`, not wall clock.
- `simTime` selects the last event with `simTime <= T`.
- Moving the cursor reconstructs state; it does not mutate the live run.

## Integrity and compatibility

| Failure                             | Behavior                                                   |
| ----------------------------------- | ---------------------------------------------------------- |
| Checksum mismatch                   | `SNAPSHOT_CHECKSUM_MISMATCH`; mark incompatible; fall back |
| Missing archive                     | `SNAPSHOT_MISSING`; fall back                              |
| Incompatible versions               | `SNAPSHOT_INCOMPATIBLE`; fall back                         |
| Sequence gap                        | `REPLAY_SEQUENCE_GAP`; fail closed                         |
| Model call during historical replay | `REPLAY_LIVE_MUTATION_FORBIDDEN`                           |

## Equivalence

`stateDigest` hashes normalized domain projection fields and excludes provenance.
Event-only reconstruction and snapshot+tail reconstruction of the same target must
produce equal digests.

## API (read-only over live mutation)

```text
GET  /api/v1/replay/runs/{runId}/state
GET  /api/v1/replay/runs/{runId}/cursor
GET  /api/v1/replay/runs/{runId}/diff
GET  /api/v1/replay/runs/{runId}/snapshots
POST /api/v1/replay/runs/{runId}/snapshots
GET  /api/v1/replay/runs/{runId}/equivalence
GET  /api/v1/replay/runs/{runId}/diagnostic
```

Snapshot create writes artifacts only; it does not append domain events or execute actions.

## CLI

```bash
uv run aegis-replay create-snapshot --run-id <runId> [--sequence N]
uv run aegis-replay reconstruct --run-id <runId> [--sequence N] [--from-events-only]
uv run aegis-replay equivalence --run-id <runId>
uv run aegis-replay list-snapshots --run-id <runId>
uv run aegis-replay corrupt-reject-demo --run-id <runId>
uv run aegis-replay gap-detect-demo
uv run aegis-replay diagnostic-page --run-id <runId> --output /tmp/replay.html
```

## Worker

```bash
uv run aegis-worker --mode snapshot
```

Env:

- `AEGIS_SNAPSHOT_INTERVAL` (default 50)
- `AEGIS_SNAPSHOT_POLL_SECONDS` (default 5)
- `AEGIS_REPLAY_IN_MEMORY_STORAGE=true` for tests/dev without MinIO

## Phase 26 must preserve

- Historical vs live isolation
- Provenance + applied event range on every replay result
- Zero external model calls in historical mode
- Canonical replay contracts (do not fork)
- Sequence-ordered cursor shared by graph and timeline consumers
- Safe return-to-live via authoritative resync (not cached assumptions)

Phase 26 owns UI controls (`ReplayViewState`, scrubbing, bookmarks). Phase 28 owns cinematic replay. Do not implement those here.
