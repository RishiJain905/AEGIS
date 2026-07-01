# Phase 10 Handoff — Operation Silent Relay Content

## Status

`READY FOR VALIDATION`

## Implemented

Phase 10 deliverables per `docs/AEGIS-v1.0-Agent-Specs/scenario-and-simulation/10-operation-silent-relay.md`:

- Full Operation Silent Relay declarative package (`1.0.0`) with 38 assets, 8 zones, 30 relationships, 15 background generators (all 8 telemetry categories), 4 hidden causes, 7 outcome branches (4 root-cause + 3 response), branch-gated scheduled events, objectives, and 8-criterion scoring rubric
- Golden seed registry (`golden-seeds.yaml`) and expected-evidence manifest (`expected-evidence.yaml`)
- Operator briefing and presentation narrative metadata
- Generic simulation/SDK extensions: 4 telemetry plugins, weighted `branch.seed_selector`, `branchGate` on scheduled events, hidden-condition trigger/reveal runtime (ADR 0011)
- Golden replay suite for 6 registered seeds; scenario acceptance, branch-coverage, and determinism tests
- Static command-centre fixtures and screenshot capture harness for Silent Relay topology and seeded runs
- Documentation: `docs/scenarios/silent-relay.md`

## Files added

| Area             | Key paths                                                                                                                                                                                           |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scenario content | `scenarios/operation-silent-relay/manifest.yaml`, `golden-seeds.yaml`, `expected-evidence.yaml`, `briefing.md`, `presentation/overview.md`, `package.manifest.yaml`                                 |
| ADR              | `docs/AEGIS-v1.0-Agent-Specs/adrs/0011-scenario-runtime-plugins-and-branch-gating.md`                                                                                                               |
| Simulation       | `packages/simulation-domain/src/aegis_simulation_domain/branch_selection.py`                                                                                                                        |
| Scripts          | `scripts/generate-silent-relay-manifest.py`, `scripts/generate-silent-relay-graph-fixture.py`, `scripts/merge-silent-relay-shell-fixture.py`                                                        |
| Tests            | `tests/scenarios/operation_silent_relay/**`, `tests/golden-replays/operation-silent-relay/**`, `tests/unit/simulation/test_branch_selection.py`, `test_phase10_plugins.py`, `test_branch_gating.py` |
| Web fixtures     | `apps/web/fixtures/silent-relay/**`, `apps/web/scripts/capture-silent-relay-demo.mjs`                                                                                                               |
| Docs             | `docs/scenarios/silent-relay.md`, `docs/handoffs/10-operation-silent-relay-HANDOFF.md`                                                                                                              |

## Files modified

| File                                                       | Reason                                                                        |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `packages/scenario-sdk/**`                                 | New plugins, `branchGroup`, `branchGate`, `targetAssetId`, `triggerThreshold` |
| `packages/simulation-domain/**`                            | Handlers, runtime branch gating, hidden conditions, engine `0.0.0-phase10`    |
| `packages/contracts-python/**`, `packages/contracts-ts/**` | New event types, simulation snapshot fields, `WORKSPACE_VERSION`              |
| `schemas/scenario/v1/*.schema.json`                        | Regenerated from SDK models                                                   |
| `tests/golden-replays/minimal/expected_hash_seed_42.json`  | Engine version bump refresh                                                   |
| `tests/contract/fixtures/compatibility-manifest.json`      | Schema hash refresh                                                           |
| `apps/web/fixtures/shell-dataset.json`                     | Silent Relay scenario, runs, graph snapshots, alerts                          |
| `apps/web/src/app/(shell)/scenarios/page.tsx`              | Navigate to scenario-linked runs                                              |
| `apps/web/features/shell/hooks/use-shell-queries.ts`       | `useRuns` hook                                                                |
| `docs/scenario-authoring.md`, `docs/simulation.md`         | Plugin and CLI documentation                                                  |

## Files removed

None.

## Contracts introduced or changed

| Contract                         | Version            | Description                                                                                                                                                                                                |
| -------------------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Behavior plugins                 | allowlist          | `telemetry.database_query`, `telemetry.deployment_event`, `telemetry.process_activity`, `telemetry.ai_inference`                                                                                           |
| Event types                      | payload v1         | `telemetry.database.query`, `telemetry.deployment.event`, `telemetry.process.activity`, `telemetry.ai.inference`, `sim.branch.selected`, `sim.hidden_condition.triggered`, `sim.hidden_condition.revealed` |
| `ScheduledEventDefinitionV1`     | schema v1 additive | `branchGate`, `targetAssetId`                                                                                                                                                                              |
| `OutcomeBranchDefinitionV1`      | schema v1 additive | `branchGroup`                                                                                                                                                                                              |
| `HiddenConditionDefinitionV1`    | schema v1 additive | `triggerThreshold`                                                                                                                                                                                         |
| `ScheduledEventV1`               | schema v1 additive | `branchGateGroup`, `branchGateBranchId`                                                                                                                                                                    |
| `HiddenConditionStateSnapshotV1` | schema v1 additive | `triggerCount`                                                                                                                                                                                             |
| `SIMULATION_ENGINE_VERSION`      | `0.0.0-phase10`    | Engine bump                                                                                                                                                                                                |
| `WORKSPACE_VERSION`              | `0.0.0-phase10`    | Workspace parity bump                                                                                                                                                                                      |

## Database migrations

None.

## Environment and configuration changes

None.

## Generated artifacts and fixtures

- `scenarios/operation-silent-relay/package.manifest.yaml`
- `apps/web/fixtures/silent-relay/graph-snapshot-*.json`
- Golden replay artifacts: `tests/golden-replays/operation-silent-relay/expected_hash_seed_*.json`
- Screenshots: `/opt/cursor/artifacts/screenshots/10-*.png`

## Tests added

| Test                                                                              | Proves                                         |
| --------------------------------------------------------------------------------- | ---------------------------------------------- |
| `tests/scenarios/operation_silent_relay/test_validation.py`                       | Package validates                              |
| `tests/scenarios/operation_silent_relay/test_determinism.py`                      | Same seed → same hash                          |
| `tests/scenarios/operation_silent_relay/test_branch_coverage.py`                  | All causes/branches reachable; seed divergence |
| `tests/scenarios/operation_silent_relay/test_acceptance_criteria.py`              | Spec §18 evidence                              |
| `tests/scenarios/operation_silent_relay/test_scoring_manifest.py`                 | Scoring rubric valid                           |
| `tests/golden-replays/operation-silent-relay/test_silent_relay_golden_replays.py` | Per-seed golden hashes                         |
| `tests/unit/simulation/test_phase10_plugins.py`                                   | New telemetry plugins                          |
| `tests/unit/simulation/test_branch_selection.py`                                  | Weighted branch selection                      |
| `tests/unit/simulation/test_branch_gating.py`                                     | Gated events skip on mismatch                  |

**Totals:** 220 passed, 14 skipped (full suite).

## Commands executed and results

| Command                                                                                                                            | Result                                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `uv run ruff check .`                                                                                                              | **PASS**                                                                                |
| `uv run mypy apps services packages`                                                                                               | **BLOCKED** — pre-existing `apps/api/src/aegis_api/db/session.py` duplicate module path |
| `uv run pytest -q`                                                                                                                 | **PASS** — 220 passed, 14 skipped                                                       |
| `uv run aegis-scenario validate scenarios/operation-silent-relay`                                                                  | **PASS**                                                                                |
| `uv run aegis-scenario package scenarios/operation-silent-relay`                                                                   | **PASS**                                                                                |
| `uv run aegis-simulator determinism-check --scenario scenarios/operation-silent-relay --seed 1000 --steps 300`                     | **PASS** (`deterministic: true`)                                                        |
| `uv run aegis-simulator seed-divergence-check --scenario scenarios/operation-silent-relay --seed-a 1000 --seed-b 1007 --steps 300` | **PASS** (`different: true`)                                                            |
| `uv run pytest tests/golden-replays -q`                                                                                            | **PASS**                                                                                |
| `uv run pytest tests/scenarios/operation_silent_relay -q`                                                                          | **PASS**                                                                                |
| `pnpm check-contracts`                                                                                                             | **PASS**                                                                                |
| `uv run lint-imports`                                                                                                              | **PASS**                                                                                |
| `pnpm --filter @aegis/web exec node scripts/capture-silent-relay-demo.mjs`                                                         | **PASS** — 7 screenshots                                                                |

## Architecture decisions and ADRs

- **Created:** [0011-scenario-runtime-plugins-and-branch-gating.md](../AEGIS-v1.0-Agent-Specs/adrs/0011-scenario-runtime-plugins-and-branch-gating.md) (Status: **Proposed**)
- **Unchanged:** ADRs 0001–0010 except additive SDK/simulation extensions documented in ADR 0011

## Known limitations

- Scoring rubric is authored declaratively only; runtime scoring deferred to Phase 29
- Hidden cause labels not exposed in operator UI during active play
- Timeline uses fixture marks, not live `domain_events` (Phases 11–13)
- `effect.adjust_relationship_confidence` emits no domain event (pre-existing)
- Run start/stop API and WebSocket graph deltas deferred to Phases 11–13

## Deferred work

- Phase 11: Event persistence and Redis streaming
- Phase 12: WebSocket gateway
- Phase 13: Live command-centre integration
- Phase 29: Deterministic scoring execution and after-action reveal

## Risks for dependent phases

- Phase 11 must relay `sim.branch.selected` and telemetry events without re-deriving branch selection
- Phase 13 must wire run creation to scenario packages without hard-coding Silent Relay IDs in platform routes
- Engine version `0.0.0-phase10` required for checkpoint compatibility
- Golden replay artifacts must be refreshed if engine or manifest semantics change

## Acceptance criteria evidence

1. **Every cause solvable but not obvious from one signal:** `expected-evidence.yaml` defines multi-signal chains and distractor contradictions; `test_cause_signals_not_obvious_from_single_event`
2. **Golden seeds cover each cause and branch:** `golden-seeds.yaml` seeds 1000/1006/1007/1014 + response pairs 1/11; `test_golden_seeds_cover_each_cause_and_branch`
3. **Evidence supports truth and contradicts false hypotheses:** `expected-evidence.yaml` `contradictsFalseHypotheses`; `test_evidence_manifest_supports_and_contradicts`
4. **Exercises graph, scoring contracts:** Graph snapshots in shell fixtures (38 nodes); scoring manifest with 8 criteria; simulation events for graph projection in Phase 11+

## Prohibited-shortcut confirmation

No Silent Relay hard-coding in platform handlers, no LLM/random outcomes, no skipped prior tests, no unexecuted validation claims, no Phase 11–13 realtime scope absorbed.
