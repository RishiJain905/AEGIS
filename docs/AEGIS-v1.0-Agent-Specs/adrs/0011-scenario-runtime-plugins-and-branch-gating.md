# ADR 0011: Scenario Runtime Plugins and Branch Gating

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 10 (Operation Silent Relay) requires seed-selected root causes, branch-gated effect chains, additional telemetry categories, and hidden-condition runtime evaluation. Phase 09 delivered a deterministic engine with seven behavior plugins but did not wire manifest `branches` or `hiddenConditions` to runtime behavior.

Architecture rules require:

- Simulation determinism for fixed scenario version, seed, and configuration.
- Scenario content remains declarative and untrusted.
- No scenario-specific hard-coding in platform code.

## Decision

1. **Additive telemetry plugins:** Register `telemetry.database_query`, `telemetry.deployment_event`, `telemetry.process_activity`, and `telemetry.ai_inference` in the Scenario SDK allowlist with typed configs and matching deterministic handlers in `aegis_simulation_domain`.

2. **Weighted branch selection:** Enhance `branch.seed_selector` to select manifest `OutcomeBranchDefinitionV1` entries filtered by `branchGroup`, using seeded RNG stream `branch.seed_selector:{branchGroup}`. Store selected manifest branch IDs in `world.selectedBranches`. Emit `sim.branch.selected`.

3. **Branch-gated scheduled events:** Add optional `branchGate` on authoring `ScheduledEventDefinitionV1` and propagate to runtime `ScheduledEventV1`. Events whose gate does not match `selectedBranches` are dequeued without side effects.

4. **Hidden-condition runtime:** Track `triggerCount` per condition. Increment on telemetry from `triggerRefs` (generators or scheduled events). When `triggerThreshold` is met, set `triggered` and emit `sim.hidden_condition.triggered`. When `triggered` or `revealAfterSimSeconds` elapses, set `revealed` and emit `sim.hidden_condition.revealed` (condition ID only).

5. **Engine version:** Bump `SIMULATION_ENGINE_VERSION` to `0.0.0-phase10`. Golden replay artifacts must be refreshed.

6. **Additive manifest fields only:** `branchGroup` on branches, `branchGate` on scheduled events, `triggerThreshold` on hidden conditions — no `schemaVersion` bump.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Hard-code Silent Relay branches in simulation engine | Violates scenario-agnostic platform rule |
| Use only existing seven plugins | Cannot model required telemetry categories credibly |
| Interpret `triggerCondition` strings at runtime | Non-deterministic / prompt-like semantics |
| Skip hidden-condition evaluation | Fails Phase 10 acceptance criteria |

## Consequences

- Phase 10 authors Operation Silent Relay declaratively using new capabilities.
- Golden replay hashes change with engine version bump.
- New event types require `EventTypeRegistry` updates and contract parity.
- Checkpoint snapshots include `triggerCount` on hidden conditions.

## Approval

- [ ] Project owner
