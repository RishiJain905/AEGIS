# ADR 0036 — Asset Security Posture and Applied Controls Are Separate Facts

## Status

Accepted

## Context

`AssetState` carried a single `status` string, and `effect.set_asset_status` — the one
plugin every operator, agent, and authored consequence action goes through — overwrote it.
Two unrelated vocabularies were writing to that field:

- **Security posture**, driven by the attacker and the scenario baseline, in the
  `NodeStatus` vocabulary (`normal` / `suspicious` / `under_investigation` / `contained` /
  `compromised`). A kill-chain technique sets it when it compromises its anchor.
- **Applied control**, driven by the defender's response toolkit, in the richer
  `ContainmentStatus` vocabulary (`observed`, `heightened_monitoring`, `isolated`,
  `access_restricted`, `credentials_revoked`, `restarting`, `rolling_back`, `contained`,
  `quarantined`). `aegis_policy.commands.COMMAND_STATUS_MAP` maps each allowlisted command
  to exactly one of these.

Because both wrote the same field, the second write destroyed the first. Running **Observe**
on a compromised asset replaced `compromised` with `observed`: the world state no longer
recorded that there was an intrusion at all. The consequences ran deep, because the whole
attacker model is derived from world state rather than from action events (deliberately, so
a live runtime and a rebuilt one agree):

- `assess_disruption` stopped seeing the campaign's foothold, so the kill-chain engine
  behaved as if the attacker had never been there.
- Business-disruption scoring and the after-action lost the record of what was compromised
  and when.
- Every disruptive control had the same shape of bug: isolating a compromised host left the
  world unable to say *why* it had been isolated.

A separate complaint from the same root: **Observe had no mechanical effect at all.**
Putting an asset under observation renamed its status and changed nothing about the
simulation — no extra telemetry, no faster detection, nothing the operator could feel.

## Decision

1. **The world holds both facts.** `AssetState.status` narrows to the security posture and
   a new `AssetState.applied_controls: tuple[str, ...]` holds the defensive controls in
   application order, deduplicated. Neither can overwrite the other.

2. **One entry point routes by vocabulary.** `AssetState.apply_status(status)` puts a
   control value into `applied_controls` and anything else into `status`. Every path that
   applies a status goes through it — the live plugin handler, the cold rebuild that
   re-applies persisted effect events, and the ghost-branch engine — so a rebuilt runtime
   and a live one are identical. `AssetState.lift_controls()` is the inverse, present
   because the proportionality model already assumes lifted containment stops counting.

3. **`contained` is classified as a control**, resolving the one value the two vocabularies
   share. It is what an action *does* to an asset, and the disruption model has always read
   it as foothold-severing.

4. **Composition happens only at projection time.** `project_effective_status(posture,
   controls)` in `aegis_contracts.killchain` (mirrored as `projectEffectiveStatus` in
   `@aegis/contracts-ts`) produces the single `NodeStatus` a `GraphNodeV1` exposes:
   - any containing control wins and reads `contained` — the operator's answer to the
     compromise is the salient fact, and the compromise itself is still in world state;
   - otherwise a non-baseline posture wins, so an observed compromise reads `compromised`;
   - otherwise an observation control on a clean asset reads `under_investigation`.

5. **`GraphNodeV1` additionally carries `appliedControls`** (additive, `schemaVersion`
   stays 1) so the inspector can render "compromised" *and* "observed" instead of forcing
   the projection to pick a winner.

6. **Disruption reads controls, never posture.** `FOOTHOLD_SEVERING_STATUSES` and friends
   are now set-intersected against `applied_controls`. Authored reaction preconditions match
   against *either* field, since rules legitimately watch both.

7. **The event payload is unchanged.** `sim.asset.status_changed` keeps carrying the single
   applied value. Every consumer that rebuilds state from the stream re-derives the split
   with the same shared helper, which means runs persisted *before* this change replay into
   the correctly composed world with no migration and no payload versioning. Checkpoints
   gain an additive `appliedControls`; a pre-split checkpoint is upgraded on restore by
   moving a control value out of `status` and projecting the posture it implies.

8. **Observe becomes mechanically real via telemetry cadence.** An asset under an
   observation control has its generator interval halved
   (`OBSERVATION_CADENCE_DIVISOR = 2`), so every detection window sees twice the telemetry
   for it, rate-based rules cross their thresholds sooner, and the alert — and with it
   fog-of-war disclosure — arrives earlier.

   The rejected alternative was raising the *probability* of anomalous telemetry on watched
   assets. Watching an asset must not change what is happening on it: fabricating failures
   because someone is looking is a lie the scoring layer would then reward. Cadence changes
   only how much of what is already true reaches the defender. It is also the cheapest
   deterministic lever — it consumes no additional RNG draw, is a pure function of world
   state at reschedule time, and leaves the authored `interval_sim_seconds` intact so
   lifting the control restores the original cadence.

   The other rejected alternative was having observation directly lift fog of war on the
   asset. Observe is a Class 0 read-only action requiring no approval, so disclosure-on-
   observe would let an operator reveal the entire scenario for free.

9. **Fog of war redacts the posture, never the controls.** Disclosure is a property of the
   *asset* — an operator acting on a still-fogged asset is entirely ordinary — so both
   redaction paths now split the same way the world does:

   - `redact_graph_snapshot` replaces the posture with the baseline and *recomposes* with
     the node's `applied_controls`, so a fogged asset the operator has isolated still reads
     `contained`;
   - the live gateway (`RunDisclosureTracker.redact`) forwards a `sim.asset.status_changed`
     carrying a control value unchanged, and rewrites only posture values.

   Before the split there was one field, so redacting it blanked the operator's own action
   along with the attacker's: observing or isolating a fogged host produced no visible
   change at all, which is the "Observe does nothing" complaint again, on exactly the assets
   where it matters most. A control value originates in the operator's own approved command
   and says nothing about the attacker, so forwarding it discloses nothing.

10. **A technique may not author a control as its `compromiseStatus`.** `contained` is the
    one value both vocabularies share, and decision 3 gives it to the defender. Authored as
    an attacker outcome it would be written to the posture by the live engine and to
    `applied_controls` by the cold rebuild — the same event stream yielding two different
    worlds, which is precisely what decision 2 exists to prevent. `KillChainTechniqueV1`
    rejects it at authoring time; it is meaningless as an attacker outcome anyway.

## Consequences

- Determinism is preserved exactly: the emitted event stream for a run without operator
  actions is byte-identical, and the golden replay artifacts are **unchanged**.
- The after-action, scoring, and ghost-branch layers can now answer "what was compromised,
  and what did we do about it" as two questions. `GhostOutcomeV1` counts an isolated
  compromised asset as both contained and compromised, which is the trade-off a
  counterfactual exists to surface.
- Ghost asset diffs compare a label that names the control and the posture under it
  (`"isolated over compromised"`), so two different response commands no longer look
  identical just because both compose to `contained`.
- Scenario authors can no longer reset an asset by writing `status: normal` over a
  containment; clearing controls is `lift_controls()`, which has no allowlisted command yet.
- An asset can accumulate several controls. Business-disruption cost takes the maximum
  weight rather than summing, so cost never double-counts.

## Deferred

- No allowlisted command lifts a control (un-isolate / stand down). The model supports it;
  the command surface, its action class, and its kill-chain effect are unspecified.
- `restarting` / `rolling_back` remain sticky rather than expiring after a sim-time
  interval, which is the behaviour they had before this change.

- The browser reducer keeps no separate posture: `GraphNodeV1` exposes only the composed
  status, so `event-projector` composes each delta against the previous *composed* value.
  Every case reachable today lands on the same answer, and an authoritative snapshot
  refetch resets it regardless. It would only diverge once a control could be lifted
  mid-run, which is itself deferred above; the fix at that point is a posture field on the
  node, not more client-side inference. The Python replay projector already tracks posture
  separately and needs no change.

- The after-action timeline (`aegis_reports.timeline`) still reports the raw applied value
  as an entry's `status`, so a containment reads `isolated` there rather than `contained`.
  Left alone deliberately: in a debrief, naming the control the operator ran is the more
  useful of the two, and nothing styles that field against the `NodeStatus` vocabulary.

## References

- `packages/contracts-python/src/aegis_contracts/killchain.py` — vocabulary and projection
- `packages/contracts-ts/src/graph.ts` — TypeScript mirror
- `packages/simulation-domain/src/aegis_simulation_domain/world_state.py` — `AssetState`
- `packages/simulation-domain/src/aegis_simulation_domain/disruption.py` — control-derived disruption
- `packages/simulation-domain/src/aegis_simulation_domain/disclosure.py` — snapshot redaction
- `apps/api/src/aegis_api/websocket/disclosure.py` — live-transport redaction
- `tests/unit/simulation/test_asset_posture_composition.py` — regression cover
- `tests/unit/test_disclosure.py`, `tests/unit/test_ws_disclosure_tracker.py` — redaction cover
- ADR 0010 — Deterministic Simulation Core
- ADR 0025 — Approval Workflow
- ADR 0030 — Scoring and After-Action
