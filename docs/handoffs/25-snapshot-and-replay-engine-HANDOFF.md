# Phase 25 Handoff — Snapshot and Replay Engine

## 1. Status

`READY FOR VALIDATION`

## 2. Implemented behavior (Sections 7 and 18)

Mapped to Phase 25 spec in-scope items and acceptance criteria:

| Spec item                                                                                          | Implementation                                                                                         |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Snapshot schema/version, checksum, compression, metadata, retention                                | `ReplaySnapshotV1` / `SnapshotManifestV1`; gzip archives; SHA-256; manifest retention + trigger reason |
| Projectors (run, graph, incidents, evidence, risk, agents, proposals, approvals, actions, reports) | `services/replay/.../projectors.py` — deterministic, idempotent by `eventId`                           |
| Nearest prior snapshot + apply events to target                                                    | `ReplayReconstructionService.reconstruct`                                                              |
| Cursor, ranges, incident focus, state diff                                                         | `ReplayCursorV1` / `ReplayCursorRangeV1` / `StateDiffV1` + API/CLI                                     |
| Background snapshot jobs + corrupt/missing fallback                                                | `aegis-worker --mode snapshot`; checksum/compat fail → earlier snapshot or events from 0               |
| Replay persisted LLM/agent artifacts without model calls                                           | Projectors load refs only; `assert_historical_mode` / zero-model guard                                 |
| Live final vs reconstructed final equivalence                                                      | Golden + integration equivalence digests                                                               |
| **AC1** Golden final equals live final projection                                                  | `tests/golden-replays/test_replay_equivalence.py`, integration equivalence                             |
| **AC2** Zero external model calls in historical replay                                             | Unit acceptance + service guard                                                                        |
| **AC3** Corrupt/missing snapshots fall back safely                                                 | Unit + CLI `corrupt-reject-demo` + integration                                                         |
| **AC4** Provenance + applied event range on every result                                           | Always returned on `ReplayState` / reconstruct responses                                               |

**Explicitly not implemented:** Phase 26 scrubbing UI, Phase 27–29 cinematic/scoring, live-run mutation during replay.

## 3. Files added / modified / removed

| Area           | Key paths                                                                                                                   | Reason                                                              |
| -------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Contracts      | `packages/contracts-python/.../replay.py`, `packages/contracts-ts/src/replay.ts`, primitives/versioning, fixtures + schemas | Canonical Phase 25 contracts; `WORKSPACE_VERSION` → `0.0.0-phase25` |
| Persistence    | `migrations/versions/011_replay_snapshots.py`, ORM, `repositories/replay.py`, `object_storage.py`, UoW                      | Manifest table + object-storage port/adapters                       |
| Replay package | `services/replay/**` (`aegis_replay`)                                                                                       | Projectors, reconstruction, checksum, diff, CLI                     |
| Workers        | `services/workers/.../snapshots/runner.py`, runner mode wiring                                                              | Cadence snapshot job                                                |
| API            | `apps/api/src/aegis_api/replay/**`, `main.py`                                                                               | Read-only replay routes                                             |
| Web stub       | `apps/web/.../replay/[runId]/page.tsx`                                                                                      | Note backend exists; UI still Phase 26                              |
| Capture        | `apps/web/scripts/capture-replay-engine-demo.mjs`                                                                           | Diagnostic HTML/screenshot harness                                  |
| Tests          | `tests/replay/**`, `tests/integration/replay/**`, `tests/golden-replays/test_replay_equivalence.py`                         | Unit/integration/golden/AC coverage                                 |
| Docs           | `docs/replay-engine.md`, ADR `0026-...`, this handoff                                                                       | Operator + architecture handoff                                     |
| Workspace      | root `pyproject.toml`, api/workers/persistence deps, `uv.lock`                                                              | Package wiring                                                      |

Nothing removed.

## 4. Contracts / interfaces

| Contract                                 | Version         | Notes                                                  |
| ---------------------------------------- | --------------- | ------------------------------------------------------ |
| `ReplaySnapshotV1`                       | schema v1       | Multi-domain projected state + compatibility pins      |
| `SnapshotManifestV1`                     | schema v1       | Checksum, object key, versions, event range, retention |
| `ReplayCursorV1` / `ReplayCursorRangeV1` | schema v1       | Sequence-primary cursor                                |
| `ReplayStateV1`                          | schema v1       | Full reconstructed projection + provenance             |
| `StateDiffV1`                            | schema v1       | Structural diff between cursors/states                 |
| `ReplayProvenanceV1`                     | schema v1       | Snapshot id/sequence + applied range + mode            |
| `ReplayEquivalenceResultV1`              | schema v1       | Digest comparison result                               |
| Runtime id `rps_`                        | —               | `ReplaySnapshotId`                                     |
| `WORKSPACE_VERSION`                      | `0.0.0-phase25` | Compatibility bump                                     |

Stable error codes: `SNAPSHOT_CHECKSUM_MISMATCH`, `SNAPSHOT_INCOMPATIBLE`, `SNAPSHOT_MISSING`, `REPLAY_SEQUENCE_GAP`, `REPLAY_DUPLICATE_EVENT`, `REPLAY_LIVE_MUTATION_FORBIDDEN`.

Spec path `packages/replay-contracts/**` maps to shared contracts packages (ADR 0002 / Phases 23–24 precedent).

## 5. Migrations, env, fixtures, commands

**Migration:** `011_replay_snapshots.py` → table `replay_snapshot_manifests`.

**Env:**

| Variable                                           | Purpose                                            |
| -------------------------------------------------- | -------------------------------------------------- |
| `AEGIS_SNAPSHOT_INTERVAL`                          | Sequence cadence (default 50)                      |
| `AEGIS_SNAPSHOT_POLL_SECONDS`                      | Worker poll interval                               |
| `AEGIS_REPLAY_IN_MEMORY_STORAGE`                   | In-memory object store (tests)                     |
| `AEGIS_REPLAY_STORAGE_DIR`                         | Filesystem object store root (demos without MinIO) |
| Standard S3/MinIO settings via persistence adapter | Production object storage                          |

**Fixtures:** `tests/contract/fixtures/valid/replay_*.json`, `snapshot_manifest_v1.json`, `state_diff_v1.json` + generated schemas.

**Operational commands:**

```bash
uv run alembic upgrade head
uv run aegis-worker --mode snapshot
uv run aegis-replay create-snapshot --run-id <runId>
uv run aegis-replay reconstruct --run-id <runId>
uv run aegis-replay equivalence --run-id <runId>
uv run aegis-replay diagnostic-page --run-id <runId> --output /tmp/replay.html
```

API prefix: `/api/v1/replay/...` (state, cursor, diff, snapshots, equivalence, diagnostic).

## 6. Tests and what they prove

| Suite                                             | Proves                                                                                |
| ------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `tests/replay/test_projectors.py`                 | Deterministic multi-domain projection from events                                     |
| `tests/replay/test_checksum_and_diff.py`          | Canonical checksum + structural diff                                                  |
| `tests/replay/test_service_unit.py`               | Reconstruct, cadence, gap, isolation guards                                           |
| `tests/replay/test_acceptance_criteria.py`        | AC1–AC4 mapped explicitly                                                             |
| `tests/integration/replay/test_replay_engine.py`  | Postgres + storage: snapshot → from-0 → snapshot+tail → equivalence; corrupt fallback |
| `tests/golden-replays/test_replay_equivalence.py` | Live-final vs reconstructed-final digest equivalence                                  |
| `pnpm check-contracts`                            | Python/TS/fixture/schema parity for new contracts                                     |

## 7. Exact validation commands and results

| Command                                                                                                  | Result                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm check-contracts`                                                                                   | **PASS**                                                                                                                                     |
| `pnpm format:check`                                                                                      | **PARTIAL** — Phase 25 files Prettier-clean; workspace-wide still fails on pre-existing regenerated schema JSON debt                         |
| `pnpm lint`                                                                                              | **PASS**                                                                                                                                     |
| `pnpm typecheck`                                                                                         | **PASS**                                                                                                                                     |
| `pnpm test`                                                                                              | **PASS** (web/UI/graph packages; 59 web tests)                                                                                               |
| `pnpm build`                                                                                             | **PASS**                                                                                                                                     |
| `uv run ruff check` (Phase 25 paths + contracts `__init__`)                                              | **PASS**                                                                                                                                     |
| `uv run mypy apps services packages`                                                                     | **KNOWN ISSUE** — duplicate module path in `aegis_agents.runtime.factory` (pre-existing)                                                     |
| `uv run pytest -q --ignore=tests/integration`                                                            | **PASS** (756 passed, 2 skipped)                                                                                                             |
| `uv run pytest tests/replay tests/integration/replay tests/golden-replays/test_replay_equivalence.py -q` | **PASS** (25 tests)                                                                                                                          |
| `AEGIS_INTEGRATION_POSTGRES=1 uv run pytest tests/integration -q`                                        | **48 passed**, **2 failed** in `tests/integration/agents/*` (non-ULID `trc_*` ids) — **pre-existing** on base; replay integration tests pass |
| `docker compose up -d postgres redis minio`                                                              | **ENV CAVEAT** — Docker unavailable; local Postgres 16 + Redis; filesystem object storage for demos (`AEGIS_REPLAY_STORAGE_DIR`)             |
| `uv run alembic upgrade head`                                                                            | **PASS** through `011`                                                                                                                       |
| Diagnostic capture + screenshots/recording                                                               | **PASS** — artifacts under `/opt/cursor/artifacts/screenshots/25-*` and `videos/25-replay-cursor-movement.webm`                              |

Demo run: Silent Relay `run_01ARZ3NDEKTSV4RRFFQ69G5FD0` (seed 1000, 80 steps, 81 events). Equivalence PASS; corrupt checksum reject; sequence gap detect; live mutation false; graphNodes=12 via telemetry projection.

## 8. Architecture decisions and ADRs

- **Created:** [0026-snapshot-and-replay-engine.md](../AEGIS-v1.0-Agent-Specs/adrs/0026-snapshot-and-replay-engine.md) (Status: **Proposed**)
- Distinguishes `GraphSnapshotV1`, `SimulationCheckpointV1`, and `ReplaySnapshotV1`
- Operator doc: [`docs/replay-engine.md`](../replay-engine.md)
- Cross-refs: ADR 0002, 0003, 0010, 0012, 0014; architecture §11 / §17

## 9. Known limitations and deferred work

- Silent Relay persisted sim runs emit mostly telemetry/lifecycle events; incidents/proposals/approvals are empty unless seeded — multi-domain projectors covered by unit/integration fixtures
- No Docker/MinIO in this cloud environment; demos used `FilesystemObjectStorage`; `S3ObjectStorageAdapter` is present for real MinIO
- Pre-existing `mypy` duplicate-module path issue remains
- Regenerated JSON schemas may still fail workspace-wide `pnpm format:check` (Prettier debt)
- Replay UI page remains a Phase 26 placeholder by design (stub text only updated)

**Deferred:** Phase 26 scrubbing UI / `ReplayViewState`, Phase 27–28 cinematic, Phase 29 scoring UX.

## 10. Risks and instructions for dependent phases (esp. Phase 26)

**Phase 26 must preserve:**

- Historical vs live isolation (never call `append_event` / approve / execute from replay UI)
- Provenance + applied event range on every reconstruct
- Zero external model calls in historical mode
- Canonical replay contracts (do not fork into a second package)
- Sequence-ordered cursor shared by graph and timeline
- Safe return-to-live via authoritative resync

Consume: `ReplayStateV1`, `ReplayCursorV1`, `ReplayProvenanceV1`, `StateDiffV1`, `/api/v1/replay/...`.

## 11. Acceptance-criterion evidence

| Criterion                                                      | Evidence                                                                                             |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Golden final replay equals live final projection               | Golden + integration equivalence; diagnostic `25-replay-equivalence.png`; digests match for demo run |
| Historical replay performs zero external model calls           | `test_acceptance_criteria.py` + service guard; no provider invocation in projectors                  |
| Corrupt/missing snapshots fall back safely                     | Unit/integration + `corrupt-reject-demo`; screenshot `25-replay-corrupt-reject.png`                  |
| Every replay result exposes provenance and applied event range | Reconstruct always attaches `ReplayProvenanceV1`; API/CLI/diagnostic show mode + ranges              |

Visual evidence (diagnostic harness, not Phase 26 UI):

- `/opt/cursor/artifacts/screenshots/25-replay-diagnostic-harness.png`
- `/opt/cursor/artifacts/screenshots/25-replay-silent-relay-history.png`
- `/opt/cursor/artifacts/screenshots/25-replay-snapshot-metadata.png`
- `/opt/cursor/artifacts/screenshots/25-replay-from-events.png`
- `/opt/cursor/artifacts/screenshots/25-replay-from-snapshot-tail.png`
- `/opt/cursor/artifacts/screenshots/25-replay-equivalence.png`
- `/opt/cursor/artifacts/screenshots/25-replay-corrupt-reject.png`
- `/opt/cursor/artifacts/screenshots/25-replay-sequence-gap.png`
- `/opt/cursor/artifacts/screenshots/25-replay-live-isolation.png`
- `/opt/cursor/artifacts/screenshots/25-replay-api-domains.png`
- `/opt/cursor/artifacts/videos/25-replay-cursor-movement.webm`

## 12. Confirmation — no prohibited shortcuts

- Production-path projectors, reconstruction, persistence, worker, API, and CLI are implemented (not stubs)
- Snapshots are acceleration only; `domain_events` remain authoritative
- No Phase 26 UI controls, cinematic replay, or live mutation during replay
- Canonical contracts live only in shared packages
- Existing tests were not deleted or loosened to pass
- Validation commands listed above were executed in this environment (Docker caveat documented honestly)
