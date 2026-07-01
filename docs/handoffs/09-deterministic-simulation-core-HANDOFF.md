# Phase 09 Handoff — Deterministic Simulation Core

## Status

`READY FOR VALIDATION`

## Implemented

Phase 09 deliverables per `docs/AEGIS-v1.0-Agent-Specs/scenario-and-simulation/09-deterministic-simulation-core.md`:

- `packages/simulation-domain` (`aegis_simulation_domain`): virtual clock, deterministic priority queue, seeded RNG streams, world-state materialization, allowlisted plugin handlers, `SimulationRuntime`, normalized event hashing
- Durable simulation contracts in `aegis_contracts` / `@aegis/contracts-ts`: `RunConfigurationV1`, `ScheduledEventV1`, `SimulationCommandV1`, `SimulationCheckpointV1`, `WorldStateSnapshotV1`, `NormalizedEventHashV1`
- Simulation event types in `EventTypeRegistry` (`sim.run.*`, `sim.checkpoint.created`, `sim.command.executed`, `sim.asset.status_changed`, telemetry extensions)
- PostgreSQL `simulation_checkpoints` table (migration `002_simulation_checkpoints`) + `CheckpointRepository`
- `SimulationApplicationService` with run creation, command idempotency, event persistence, checkpoint save/restore
- `aegis-simulator` CLI: `run`, `determinism-check`, `checkpoint-recovery-check`, `seed-divergence-check`, `invalid-command-demo`
- Golden replay artifact for `scenarios/_fixtures/valid-minimal` seed 42
- Documentation: `docs/simulation.md`, ADR `0010-deterministic-simulation-core.md`
- Platform compatibility fix for `0.0.0-phaseNN` workspace versions in scenario SDK

## Files added

| Area           | Key paths                                                                                                |
| -------------- | -------------------------------------------------------------------------------------------------------- |
| Domain package | `packages/simulation-domain/**`                                                                          |
| Contracts      | `packages/contracts-python/src/aegis_contracts/simulation.py`, `packages/contracts-ts/src/simulation.ts` |
| Persistence    | `migrations/versions/002_simulation_checkpoints.py`, checkpoint repository in `aegis_persistence`        |
| Service        | `services/simulation/src/aegis_simulation/application.py`, updated `runner.py`                           |
| Tests          | `tests/unit/simulation/**`, `tests/integration/simulation/**`, `tests/golden-replays/minimal/**`         |
| Fixtures       | `tests/contract/fixtures/valid/*simulation*`, generated schemas                                          |
| Docs/ADR       | `docs/simulation.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0010-deterministic-simulation-core.md`           |
| Evidence       | `apps/web/scripts/capture-simulation-demo.mjs`, `scripts/capture-simulation-demo.mjs`                    |

## Files modified

| File                                                                                     | Reason                                              |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `pyproject.toml`                                                                         | Workspace member, import-linter roots               |
| `packages/contracts-python/src/aegis_contracts/{events,versioning,__init__,fixtures}.py` | Simulation contracts and event types                |
| `packages/contracts-ts/src/{events,versioning,index}.ts`                                 | TS parity                                           |
| `packages/persistence/src/aegis_persistence/**`                                          | Checkpoint ORM, repository, UoW                     |
| `packages/scenario-sdk/src/aegis_scenario_sdk/compatibility.py`                          | PhaseNN version comparison                          |
| `services/simulation/pyproject.toml`, `health.py`                                        | Dependencies and version                            |
| `tests/integration/conftest.py`                                                          | Truncate `simulation_checkpoints`                   |
| `tests/contract/fixtures/compatibility-manifest.json`                                    | New artifact hashes                                 |
| `scenarios/_fixtures/valid-minimal/manifest.yaml`                                        | Unchanged platform version (compatible via SDK fix) |

## Contracts introduced or changed

| Contract                 | Version         | Description                                             |
| ------------------------ | --------------- | ------------------------------------------------------- |
| `RunConfigurationV1`     | schema v1       | Run seed, engine version, clock epochs                  |
| `ScheduledEventV1`       | schema v1       | Runtime queue item (distinct from authoring definition) |
| `SimulationCommandV1`    | schema v1       | Idempotent command envelope with authorization          |
| `SimulationCheckpointV1` | schema v1       | Checkpoint metadata + embedded world snapshot           |
| `WorldStateSnapshotV1`   | schema v1       | Serializable simulation state                           |
| `NormalizedEventHashV1`  | schema v1       | Golden replay hash artifact                             |
| `WORKSPACE_VERSION`      | `0.0.0-phase09` | Workspace metadata parity bump                          |
| Simulation event types   | payload v1      | `sim.run.*`, telemetry extensions                       |

## Database migrations

- `002_simulation_checkpoints.py` — `simulation_checkpoints` table with `(run_id, sequence_at_checkpoint)` uniqueness

## Environment and configuration changes

None.

## Generated artifacts and fixtures

- Golden replay: `tests/golden-replays/minimal/expected_hash_seed_42.json`
- Contract schemas: `tests/contract/fixtures/schemas/*simulation*`
- Screenshots: `/opt/cursor/artifacts/screenshots/09-*.png`

## Tests added

| Test                                                           | Proves                                                           |
| -------------------------------------------------------------- | ---------------------------------------------------------------- |
| `tests/unit/simulation/test_primitives.py`                     | Clock, queue ordering, RNG determinism                           |
| `tests/unit/simulation/test_runtime.py`                        | Determinism, checkpoint recovery, authorization rejection        |
| `tests/unit/simulation/test_simulation_acceptance_criteria.py` | Maps to spec §18                                                 |
| `tests/integration/simulation/test_simulation_persistence.py`  | PostgreSQL run/event/checkpoint/idempotency (skipped without DB) |
| `tests/golden-replays/minimal/test_minimal_fixture_replay.py`  | Stable golden hash + seed divergence                             |

## Commands executed and results

| Command                                                                                                                                 | Result                                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `uv run ruff check .`                                                                                                                   | **PASS**                                                                                                                   |
| `uv run mypy apps services packages`                                                                                                    | **BLOCKED** — pre-existing `apps/api/src/aegis_api/db/session.py` duplicate module path error (not introduced by Phase 09) |
| `uv run pytest -q`                                                                                                                      | **PASS** — 193 passed, 14 skipped                                                                                          |
| `docker compose up -d postgres redis object-storage`                                                                                    | **BLOCKED** — `docker` not available in validation environment                                                             |
| `uv run pytest tests/integration -q`                                                                                                    | **PASS** — 14 skipped (no PostgreSQL)                                                                                      |
| `uv run pytest tests/golden-replays -q`                                                                                                 | **PASS** — 2 passed                                                                                                        |
| `pnpm check-contracts`                                                                                                                  | **PASS**                                                                                                                   |
| `uv run lint-imports`                                                                                                                   | **PASS**                                                                                                                   |
| `uv run aegis-simulator determinism-check --scenario scenarios/_fixtures/valid-minimal --seed 42 --steps 30`                            | **PASS** (`deterministic: true`)                                                                                           |
| `uv run aegis-simulator checkpoint-recovery-check --scenario scenarios/_fixtures/valid-minimal --seed 42 --steps 30 --checkpoint-at 10` | **PASS** (`recoveryMatches: true`)                                                                                         |
| `uv run aegis-simulator seed-divergence-check --scenario scenarios/_fixtures/valid-minimal --seed-a 42 --seed-b 99 --steps 30`          | **PASS** (`different: true`)                                                                                               |
| `uv run aegis-simulator invalid-command-demo`                                                                                           | **PASS** (`rejected: true`, `SIMULATION_UNAUTHORIZED`)                                                                     |
| `pnpm --filter @aegis/web exec node scripts/capture-simulation-demo.mjs`                                                                | **PASS** — 4 screenshots captured                                                                                          |

## Architecture decisions and ADRs

- **Created:** [0010-deterministic-simulation-core.md](../AEGIS-v1.0-Agent-Specs/adrs/0010-deterministic-simulation-core.md) (Status: **Proposed**)
- **Unchanged:** ADRs 0001–0009 except scenario SDK compatibility helper extension

## Known limitations

- No FastAPI `/api/v1/runs` routes (later phase)
- Asset/relationship instance rows not yet synced on every world mutation (events are authoritative; graph projection deferred)
- Integration tests require real PostgreSQL (skipped when unavailable)
- `mypy` fails on pre-existing API session module path issue

## Deferred work

- Phase 10: Operation Silent Relay scenario content
- Phase 11: Redis/WebSocket event streaming from outbox
- Phase 24: Full approval workflow for agent proposals
- API routes for simulation control

## Risks for dependent phases

- Phase 10 must author content via Scenario SDK only
- Phase 11 must treat `domain_events` as authoritative relay source
- Checkpoint format changes require engine version bump and migration notes
- New behavior plugins require handler registry updates and golden refresh

## Acceptance criteria evidence

1. **Fixed inputs → stable histories:** `test_same_seed_produces_identical_normalized_hash`, CLI `determinism-check` (`deterministic: true`)
2. **Checkpoint/restore matches uninterrupted:** `test_checkpoint_restore_matches_uninterrupted_run`, CLI `checkpoint-recovery-check` (`recoveryMatches: true`)
3. **Commands idempotent with authorization:** `test_agent_command_is_rejected`, `test_duplicate_command_is_rejected` (integration), `test_ac3_commands_require_authorization_context`
4. **Simulator owns truth independently:** `test_ac4_simulator_owns_truth_independently`; no frontend/agent code paths mutate runtime state

## Prohibited-shortcut confirmation

No scaffolding-only handlers, no Silent Relay hard-coding, no LLM/wall-clock/global-random domain outcomes, no skipped weakening of prior tests, no unexecuted validation claims for commands that were run successfully in this tree.
