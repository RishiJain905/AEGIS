# ADR 0037: Incidents are opened deterministically by the detection engine

## Status

Accepted (v1.0 — live-run investigation chain, 2026-07-31)

## Context

A live run raised alerts and never produced an incident. Every downstream
subsystem that keys off a case therefore stayed dark: BASTION's containment tool
requires an open incident, so the operator could never reach a proposal; the
after-action dossier and the reports timeline reconstruct incidents from the
event stream and so had nothing to render; the incident queue was empty for the
whole engagement.

The cause was that no reachable code path opened one. Three facts combined:

1. `AutonomyPoller` (`apps/api/.../autonomy/poller.py`) reacts to each newly
   persisted alert by calling `AutonomyTriageService.on_new_alert`, which is
   deliberately **enqueue-only** — it creates a QUEUED agent task and returns.
   It never reaches `WatchtowerCoordinator.trigger_for_run`, the only function
   containing `_resolve_incident` (the sole production incident-opening code).
2. The agent tool registry exposes no incident-creating tool, by design.
3. `TaskExecutor` derives `run_scoped = task.incident_id is None` and skips role
   post-processing for run-scoped tasks. Autonomy tasks are created on a
   long-lived run-scoped lane session per `(run, role)`, so `incident_id` was
   always `None` and `WatchtowerRoleHandler.post_process` — which writes the
   triage row — could never run for an autonomy turn.

`trigger_for_run` was reachable only from
`POST /runs/{id}/investigation/trigger-watchtower`, which the web app never
calls, and from a local harness script. The single incident a live run could
produce was the operator anchor from `_ensure_operator_incident`, created as a
side effect of pinning a hypothesis or ordering containment — an anchor with no
alerts attached, not a case.

Two constraints frame the fix. Architecture §20 requires core CI to pass without
an external LLM. Architecture §13 makes incident correlation the alert-and-
incident engine's responsibility, using transparent rules over shared assets,
temporal proximity and graph distance.

## Options considered

1. **Have the autonomy poller call `WatchtowerCoordinator.trigger_for_run`.**
   Rejected: it contradicts the poller's defining property. The poller is
   enqueue-only precisely so a burst of alerts cannot stall the loop behind a
   model call, and `trigger_for_run` runs triage. It also leaves incident
   existence gated on the provider being up.

2. **Add an incident-creating agent tool.** Rejected: it raises a policy-class
   question with no good answer. Opening a case is not read-only (Class 0) and
   not obviously an analysis write (Class 1), yet gating it behind human approval
   as a Class 2 state change would make the incident queue depend on an approval
   the operator has no context to give. It also puts the existence of the core
   domain object behind schema-constrained model output.

3. **Persist the incident when triage completes.** Rejected: strictly better than
   the status quo but still provider-coupled. A provider outage, a malformed
   structured response, or an exhausted token budget still yields a run with
   alerts and no cases — the exact failure being fixed.

4. **Open incidents deterministically in the detection layer. — CHOSEN.**

## Decision

**Incident creation is a deterministic function of persisted detection output. No
model is involved.**

1. **Correlation runs inside `run_detection_for_events`.** After alert candidates
   are persisted, `aegis_incidents.correlation.open_correlated_incidents` runs in
   the same transaction, so the incident row, its `incident.created` event and
   the outbox entry commit together (architecture §7). Attribution is
   `ActorRef(SYSTEM, "asset:detection-engine")`, the same actor `alert.created`
   already uses.

2. **Cases are keyed to an asset, with a derived id.**
   `deterministic_incident_id(run_id, asset_id)` returns
   `incident:inc_det_<sha256(run|asset)[:20]>`. Determinism follows from the id
   being a pure function of its inputs: the same scenario version and seed open
   the same incident ids. Dedupe follows from the same property — an asset's case
   can only exist once, and any reader can derive it without a query, which is
   what lets WATCHTOWER find the case to enrich.

3. **Two transparent correlation rules.**
   - `correlation-alert-threshold`: alerts on an asset reaching
     `DEFAULT_ALERT_THRESHOLD` (**1**) open that asset's case.
   - `correlation-compromise-confirmed`: an asset that reaches a compromised
     status in the event stream **and** already carries at least one alert opens
     (or is promoted to) a confirmed-compromise case.

   The threshold is 1 because that is what the scenario produces. Measured across
   all six Operation Silent Relay golden seeds to the full live horizon (1500
   sim-seconds), every run raises exactly three alerts and never more than one
   per asset. A threshold of 2 opened zero cases on five of six seeds, including
   runs the attacker wins by exfiltration. The grouping work correlation exists
   to do is still real and still transparent — the case is keyed to the asset, so
   every later alert on it joins that case rather than spawning another.

   Ground truth alone never opens a case. `sim.asset.status_changed` is consulted
   only to *confirm* an asset detection has already alerted on; opening from the
   world model would hand the operator a compromise detection never found and
   collapse the scenario's fog of war.

4. **Follow-on alerts attach; confirmed compromise promotes.** A later alert on
   an asset with an open case is merged into that case's `alertIds`, and a case
   opened on a lead is retitled when the campaign confirms it. Both emit
   `incident.state_changed` carrying the full incident, because the event
   registry has exactly two incident types and replay rebuilds incidents from
   events — a silently updated row desynchronises it. The replay projector now
   merges `alertIds` and `title` from that payload instead of ignoring them.

5. **WATCHTOWER becomes an enricher.** `AutonomyTriageService.on_new_alert`
   resolves the asset's already-open case with a read-only lookup and scopes the
   enqueued task to it, so the turn's role post-processing writes triage against
   that incident. The lookup deliberately has no create branch, mirroring the
   `_require_incident` / `_resolve_incident` split in `OperatorActionService`: a
   triage turn that could open a case would put incident existence back behind a
   model call. No case yet simply leaves the task run-scoped, which is the
   pre-existing behaviour.

6. **Shared builders move to the contracts package.**
   `build_incident_created_event`, the new `build_incident_updated_event` and
   `deterministic_incident_id` live in `aegis_contracts.incident_events`. The
   detection engine and the agent runtime are sibling services that may not
   import each other, so a builder in either would force a layering inversion or
   a second, drifting copy of the `incident.created` payload shape. No new
   contract *model* is introduced, so the Python↔TypeScript contract gate is
   unaffected.

## Consequences

- Incident existence survives a provider outage. The QA chain that failed
  (provider down → no triage → no incidents → BASTION blocked → empty report)
  no longer has a model in it up to the point a case exists.
- A normal Silent Relay run now opens roughly three cases, one per alerting
  asset — a queue the incident UI is sized for, not a flood.
- WATCHTOWER's product role narrows from "raises and triages cases" to "triages
  and enriches cases the detection engine raised". Its output still determines
  escalation and whether TRACE is chained.
- Autonomy turns scoped to an incident now use WATCHTOWER's role output schema
  rather than the compact generic step schema. `post_process` therefore defaults
  missing `escalation` / `escalationRationale` / `confidence` fields instead of
  raising, so a local model that drops one still enriches the case.
- Two executor hazards this created were closed with it: failure-driven session
  termination is now keyed on `session.incident_id` rather than
  `task.incident_id` (an incident-scoped lane turn must not terminate the shared
  autonomy lane), and autonomy turns fail soft on tool errors like chat turns do.
- **Golden replays are unaffected.** The golden harness hashes
  `SimulationRuntime.events` only; it never runs the detection pipeline, so no
  detection, alert or incident event has ever entered a golden hash. No artifact
  needed regeneration.
- A related detection defect was fixed as part of this, because correlation had
  no usable input without it: `DetectionRunState.last_alert_by_group` was keyed
  by suppression group alone, so one asset's alert suppressed the *same rule
  firing on a different asset*. In Silent Relay this hid the alert on the exact
  identity broker the campaign compromises, leaving each run with a single alert
  on an unrelated asset. It is now keyed by `(group, entity)`. Silent Relay runs
  raise 3 alerts instead of 1.

## Follow-ups (not in this change)

- Bias-guard (ORACLE) and standing-directive turns still enqueue run-scoped and
  do not enrich a case; the same lookup would apply.
- Correlation is per-asset only. Campaign-level correlation (grouping the assets
  of one campaign into a single case via graph distance or shared trace ids, per
  architecture §13) is the natural next rule and would reduce a three-case queue
  to one case with three affected assets.
- `IncidentState` transitions beyond OPEN are still driven by triage; the
  detection engine never advances a case's state.
