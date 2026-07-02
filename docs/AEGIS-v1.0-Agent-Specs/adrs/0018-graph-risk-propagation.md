# ADR 0018: Graph Risk Propagation (Phase 17)

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 17 must compute deterministic bounded graph risk with direct and propagated components, explanation paths, PostgreSQL persistence, realtime graph projection, and command-centre visualization. Phase 15 rule alerts and Phase 16 model scores seed origin signals. The Phase 05 graph snapshot remains the canonical topology source.

## Decision

1. **Engine location:** Python package `aegis-graph-risk` (`packages/graph-risk`) performs authoritative server-side propagation. TypeScript/Sigma.js consumes wire contracts and persisted scores only — no renderer-side risk math.

2. **Algorithm:** Transparent bounded multi-source BFS (`graph-risk-v1`), not a GNN or LLM analyst.

3. **Inputs:** Normalize `AlertV1` (rule) and optional `ModelScoreV1` (model) into `RiskInputV1`. Tabular detection scores remain advisory and are not replaced.

4. **Propagation equations:**
   - Edge weight: `riskContribution × confidence × relationshipTypeWeight`
   - Distance decay: `distanceDecayFactor^hopCount` (default 0.65)
   - Temporal decay: `temporalDecayFactor^(ageSeconds / halfLifeSeconds)`; resolved/expired signals contribute 0
   - Criticality factor: `1 + target.criticality × criticalityAmplifier`
   - Per-path contribution: `signalStrength × ∏ edgeWeights × distanceDecay × temporalDecay × criticalityFactor`
   - Propagated component: max over paths/sources; total = min(globalCap, direct + propagated)

5. **Cycle safety:** Hop cap, no revisiting nodes on a path, max aggregation, global cap 1.0.

6. **Contracts:** `RiskInputV1`, `AssetRiskScoreV1`, `RiskContributionV1`, `RiskExplanationPathV1`, `RiskEngineConfigV1`, `RiskProjectionDeltaV1` at schema version 1 in `aegis_contracts.risk`.

7. **Events:** `risk.score.computed` (durable score) and `risk.projection.updated` (graph overlay delta) via outbox → Redis → WebSocket.

8. **Persistence:** `asset_risk_scores` table (migration `004_asset_risk_scores`).

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| GNN risk scoring | Out of Phase 17 scope; lacks explainability guarantees |
| TypeScript propagation engine | ML/persistence pipeline is Python; snapshot is JSON contract |
| Sum aggregation across paths | Allows cycle amplification; max aggregation is bounded |
| Client-side risk derivation | Violates authoritative backend contract |

## Consequences

- Phase 18+ must preserve `graph-risk-v1` deduplication keys, algorithm version, and advisory-only semantics.
- Graph node `riskScore` updates flow through `risk.projection.updated` deltas only.
- Rollback: prior algorithm version requires new manifest + config version bump.

## Approval

- [ ] Project owner
