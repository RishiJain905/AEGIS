# AEGIS Tutorial and Simulation QA Report

**Date:** 2026-07-30 to 2026-07-31  
**Application:** `http://localhost:3000`  
**Model endpoint configured by the app:** port `8086` (`http://host.docker.internal:8086/v1`)  
**Browser:** Chrome, `AEGIS Command - Google Chrome`, maximized throughout the final pass  
**Interaction method:** Computer Use only for Windows/browser interaction. The Computer Use runtime was initialized through the tagged plugin's absolute wrapper, its guidance was read, and a read-only app/window listing plus screenshot smoke test succeeded.  
**Code changes:** None. This report is the only file added by this QA pass.

## Executive verdict

- **Computer Use:** PASS. The runtime was genuinely initialized and used for all final browser actions.
- **Tutorial:** PARTIAL / NOT READY TO SHIP. All 10 chapters could be advanced and the final launch action was reached, but the tutorial does not reliably gate progress on its objectives and can start in the wrong run context.
- **Operation Silent Relay:** FAIL / NOT VERIFIED AS A WIN. The first run reached the live header state `outcome_resolved` at sequence `327` after two containment submissions, but its after-action later showed `46.4 / 100`, grade `F`, `Failed`. A second run was investigated with all four AI roles attempted, then became stuck paused at sequence `318` after task/provider failures and never produced a terminal score.
- **Connected run sections:** FAIL. Incidents, after-action, reports, and terminal replay state were not usable for the completed run. Admin loaded, but its readiness summary is internally contradictory. Design System loaded.
- **Connected AI model:** FAIL. WATCHTOWER and TRACE requests reached `Working…`, then ended in `PROVIDER_FAILURE` / `Provider request was cancelled`; no usable structured result was returned. BASTION could not be exercised because the incident queue failed to load.

The most important release blockers are the inconsistent terminal state, unavailable incident queue, unusable after-action/report flow, replay reconstruction failure, and model requests that time out without recovery controls.

## Runs and configuration exercised

### Tutorial

- Scenario: `Tutorial Synthetic Training Scenario`
- Tutorial run observed: `run_E02AHM3GRDCYE9CDMM1PBTD3D1`
- Seed: `1000`
- Operator shown in the run: `Admin Alpha`
- The final tutorial action, `Launch Operation Silent Relay`, returned to `/scenarios`.
- Chapters 1–10 were opened and advanced. The final copy was: “This run is repeatable… You have the desk.”

The pass covered orientation, graph search/selection, view options, pause/resume, alerts, evidence, incidents, command/containment, AI role selection, and model cards. Chapters 6–10 were explicitly observed as follows:

| Chapter | Observed beats | Result |
|---|---|---|
| 6 | WARDEN’s decision; Hold the gate; The audit trail; Play it out | Advanced, but objective gating was not reliable |
| 7 | The operations rail; Two scenarios | Advanced |
| 8 | The incident queue; SCRIBE reports | Advanced even when the connected sections were unavailable |
| 9 | How the run is graded; The lane you could not see | Advanced while the report objective was still unmet |
| 10 | Replay; Admin, palette and shortcuts; That is the floor | Advanced to completion |

### Live scenario

- Scenario: `Live Operation Silent Relay`
- Run: `run_8024W2GZ4PMQ02P8FXTH840AY6`
- Seed: `1725850860`
- RNG: random server RNG
- Bias guard: enabled
- Threat tempo: enabled
- ROE: `Forward-deployed`
- Commander intent: `Protect student records; preserve evidence; investigate before containing confirmed compromise with the least disruptive action.`

The run header eventually showed `STATUS outcome_resolved`, `SIM 2026-01-01T00:06:24Z`, and `SEQ 327`. That terminal-looking result was not propagated to the after-action, reports, or replay surfaces, so the final score/win state could not be independently verified.

### Continuation run (final-pass rerun)

- Run: `run_ZBRXME4YXDCCC09MB4AV50K440`.
- Loadout: Bias guard enabled, Threat tempo enabled, ROE `Investigate`, and an evidence-preserving commander intent.
- Play approach: followed the alert/evidence trail, pinned a hypothesis, used the contextual asset actions, entered justifications, and selected proportionate reversible actions: Increase telemetry, Restrict access on Communications Gateway, Revoke service credentials on Identity Broker, and Isolate service on Service Account Vault.
- AI coverage: explicitly attempted WATCHTOWER, TRACE, ORACLE, and BASTION. The app is configured for the local model on port `8086`, but no role returned a usable successful result.
- Terminal result: the run remained `STATUS paused` at `SEQ 318`. Resume, Resync, reload, and a bounded wait did not advance simulation time; Step only produced additional agent-session/task events. No score or win state was generated.

The earlier two-turn result therefore was not a legitimate win: it was two operator containment submissions followed by a terminal-looking header, and the later after-action grade was `F`.

## Live playthrough evidence

The following sequence numbers were visible in the run tape:

| Sequence | Sim time | Event |
|---:|---:|---|
| 14 | 00:00:24 | `Unseen source activity detected` |
| 27 | 00:00:40 | Repeated unseen-source alert |
| 51 | 00:01:15 | Authentication failed for `asset:identity-svc-logistics-bot` |
| 53 | 00:01:15 | Logistics bot reported normal |
| 72 | 00:01:30 | Repeated unseen-source alert |
| 130 | 00:02:24 | API request on `asset:svc-comms-gateway` |
| 132 | 00:02:30 | Authentication failed on `asset:svc-identity-broker` |
| 134 | 00:02:30 | `asset:svc-identity-broker → compromised` |
| 142 | 00:02:40 | Authentication succeeded on `asset:svc-identity-broker` |
| 187 | 00:03:45 | `asset:svc-service-account-vault → compromised` |
| 246 | 00:05:00 | `sim.hidden_condition.triggered` |
| 247 | 00:05:00 | `sim.hidden_condition.revealed` |
| 250 | 00:05:00 | `asset:database-customer-pii → normal` |
| 297 | 00:06:00 | Authentication failed on `asset:svc-identity-broker` |
| 316 | 00:06:15 | `asset:svc-comms-gateway → compromised` |
| 327 | 00:06:24 | `telemetry.network.connection`; header surfaced `outcome_resolved` |

Actions taken while attempting to win:

1. Selected `Identity Broker` after the failed authentication and confirmed compromise evidence. Opened `Isolate service`, reviewed the consequence gate, entered a justification, and confirmed. The modal projected five severed connections, including high-criticality downstream impact, and marked the action reversible.
2. Selected `Service Account Vault` after sequence `187`, opened `Isolate service`, reviewed the one-connection impact, entered a justification, and confirmed. The action was reversible and limited to the already compromised Identity Broker connection.
3. On the lower-risk investigation path, watched principal activity and audited token issuance for `Logistics Service Bot`.
4. Sent investigation prompts to WATCHTOWER and TRACE with sequence citations. Both failed at the provider boundary; details are in BUG-008.

The Ops feed showed `operator.action.proposed` and `action.executed` for the containment orders. The live run progressed to the terminal-looking `outcome_resolved` state, but the reporting surfaces did not recognize it.

## Bugs

Severity guide: **P1** blocks or materially undermines a core workflow; **P2** is a significant correctness or usability defect; **P3** is polish or low-impact consistency.

### BUG-001 — Tutorial “Start new run” can reuse a run owned by another identity (P1)

**Area:** Scenarios → Tutorial Synthetic Training Scenario; supplementary pre-repair observation.

**Reproduction:**

1. Sign in as `Operator Alpha` using `dev-login-operator` (`user:operator-alpha`).
2. Open `/scenarios`.
3. Select `Tutorial Synthetic Training Scenario` → `Start new run`.

**Observed:** The route opened `/runs/run_E02AHM3GRDCYE9CDMM1PBTD3D1`, but the workspace showed `Something went wrong`, `Unable to load workspace data`, and `Retry`. The run GET returned HTTP 403 twice with `Not authorized to access run`. The run creation response was HTTP 200 but reported an idempotent replay and an existing `ownerUserId` of `user:acct_9020b4189b4c9d8b620eb455`, not `user:operator-alpha`.

**Expected:** Starting a tutorial run creates or selects a run owned by the authenticated user and loads its workspace without a permission error.

**Suggested fix:** Scope idempotency keys to user plus scenario, never replay a run ID across identities, and make the client clear stale run IDs when the current user changes. Add an automated test for “operator starts tutorial after another user has a prior tutorial run.”

### BUG-002 — Tutorial onboarding starts against a stopped demo/catalogue context (P1)

**Area:** Admin first visit to `/scenarios`.

**Reproduction:** Open the scenarios catalogue as Admin Alpha and follow the auto-started tutorial overlay.

**Observed:** The catalogue showed `Demo run`, `Restart training run`, and `Open demo run (stopped)`. The overlay began before a live workspace was available. Later tutorial guidance referred to run controls and the finalization objective although the demo run was stopped. The demo run observed was `run_5G5R6DDAH55SSS4ZVX33D53RX5`, seed `424242`, status `stopped`, sequence `400`.

**Expected:** First-run onboarding should either start a fresh run before describing live controls or explicitly label itself as catalogue orientation.

**Suggested fix:** Make onboarding context-aware. If the current run is stopped, offer one clear `Start training` action and attach the tutorial to the resulting run. Do not show live-run objectives until the live run has been created.

### BUG-003 — API error responses trigger CORS failures and an unbounded retry storm (P1)

**Area:** Run bootstrap/realtime degradation; supplementary pre-repair observation.

**Reproduction:** Load a run while its API requests are failing, then leave the page open.

**Observed:** Requests to `http://localhost:8000/api/v1/runs/...` and `/graph` repeatedly failed with `No 'Access-Control-Allow-Origin' header`, `ERR_FAILED`, and `TypeError: Failed to fetch`. The UI changed to `Connection offline / Realtime updates are unavailable. Showing last known fixture data.` and `Offline`. Hundreds of repeated failures accumulated (approximately 391 in the observed session).

**Expected:** Error responses retain CORS headers, retries use bounded exponential backoff, and the client stops retrying after a clear limit while offering an explicit retry/reconnect action.

**Suggested fix:** Apply CORS middleware to error paths as well as success paths; centralize retry policy with jitter and a cap; reset the backoff after a successful request; expose the next retry/reconnect state in the UI.

### BUG-004 — Paused simulation exposes a Step control that the API rejects (P2)

**Area:** Live run transport controls.

**Reproduction:** Pause the simulator and click `Step`.

**Observed:** The button remained available, the POST `/step` call returned HTTP 409 with `Cannot step run in status paused`, and no clear user-facing explanation appeared. The sequence did not advance.

**Expected:** Either stepping is supported while paused, or the button is disabled/renamed with an explanation of the required state.

**Suggested fix:** Align the button state with the server state. If stepping is intended to be a paused-mode action, change the API contract and add a test for paused stepping; otherwise disable it and explain why.

### BUG-005 — Tutorial marks the first-alert objective before the explanation is opened (P2)

**Area:** Tutorial objective tracking.

**Reproduction:** Reach the first-alert tutorial step and inspect the alert without opening its explanation.

**Observed:** `First alert raised — read the explanation before you move.` was marked met while the alert inspector still showed the generic collapsed `Explanation` area.

**Expected:** The objective should become met only after the explanation is opened, or the objective text should only require alert visibility.

**Suggested fix:** Track the explanation-open interaction explicitly and add a regression test that distinguishes alert selection from explanation disclosure.

### BUG-006 — Tutorial Next/progress controls are not gated by unmet objectives (P1)

**Area:** Tutorial overlay.

**Reproduction:**

1. At Chapter 3 beat 2, observe `Open incident from inspector` when no incident is available.
2. At Chapter 9 beat 1, observe `Let the run finalize — this clears once its report has compiled` while the report is not ready.
3. Click `Next`.

**Observed:** `Next` remained enabled in both cases, and the tutorial advanced through all 10 chapters. Chapter 9’s objective was visibly unmet, but no skip confirmation or unresolved-objective marker was shown.

**Expected:** Next should be blocked until a required objective is met, or the user should explicitly choose `Skip objective` and the tutorial should record that choice.

**Suggested fix:** Make objective requirements declarative (`required`, `optional`, `skippable`) and have the overlay render a clear disabled state, skip reason, and completion audit trail.

### BUG-007 — Containment execution is not reconciled into asset state (P1)

**Area:** Tutorial containment command and live asset inspector.

**Reproduction:** Use `Isolate host`/`Isolate service`, complete the justification gate, confirm the action, then let the workspace resync.

**Observed:** The action response was HTTP 200 with `status: executed`, `policyOutcome: approval_required`, action and approval IDs, and a visible `Action executed` toast. After resync, the selected asset still displayed `compromised` rather than a contained/isolated state. In the tutorial run, the control link also changed to `Normal — no active concerns` while the run was paused and the asset remained compromised.

**Expected:** The action result, graph node status, inspector, alerts, and connection status should converge to one authoritative state, with approval-required status clearly distinguished from executed containment.

**Suggested fix:** Reconcile action execution and approval outcome through a versioned event; update the graph and inspector atomically; show `Executed`, `Pending approval`, or `Rejected` as separate states. Add an end-to-end test from command confirmation through websocket resync.

### BUG-008 — Connected AI requests fail after a long Working state with no recovery path (P1)

**Area:** WATCHTOWER/TRACE copilot; model endpoint configured on port 8086.

**Reproduction:** On the live Silent Relay run, select WATCHTOWER and send:

> Sweep the current alerts and telemetry. Identify the most likely initial access, affected asset, confidence, and the safest next investigation step. Cite supporting sequence numbers.

Then select TRACE and send:

> Trace the unseen-source alerts and the failed authentication on identity-svc-logistics-bot. Identify the likely affected asset and next investigation step using sequences 14, 27, 51, and 72; cite uncertainty.

**Observed:** Both requests displayed `Working…`, then ended with `The last request failed.` and `Provider request was cancelled (PROVIDER_FAILURE)`; one UI state also displayed `signal timed out`. The run tape recorded `agent.task.started` and `agent.task.failed` events. No usable structured answer, citations, partial response, retry control, request ID, or provider diagnostics was shown. BASTION displayed `Draft proportionate containment (needs an open incident to propose actions)` and could not be exercised because the incident queue failed.

**Expected:** The connected model should complete within a bounded time or transition to an actionable error state with retry/cancel/provider details. A provider failure must not leave stale Working state or silently remove the structured output contract.

**Suggested fix:** Add a visible timeout countdown/state, cancel and retry actions, provider/request IDs, structured fallback output, and a model health probe. Ensure retry count and provider selection are visible. Test the configured local endpoint separately from the cloud fallback and surface which provider actually handled the request.

### BUG-009 — Active run navigation loses the current run context (P1)

**Area:** Operations rail.

**Reproduction:** While viewing `/runs/run_8024W2GZ4PMQ02P8FXTH840AY6`, click `Active run`.

**Observed:** The browser navigated to `/scenarios` rather than returning to the current run. Clicking `Active run` from `/scenarios` also stayed on `/scenarios`.

**Expected:** `Active run` should navigate to the current active run, or be disabled/renamed when no active run exists.

**Suggested fix:** Store the active run ID in the session/context and generate the rail link from it. Add tests for active, stopped, terminal, and no-run states.

### BUG-010 — Incident queue cannot load active cases (P1)

**Area:** `/incidents` and BASTION workflow.

**Reproduction:** Open `Incidents` from the live run.

**Observed:** The page showed `Incident queue`, then `Something went wrong`, `Unable to load incidents.`, and `Retry`. This prevented selecting an incident and blocked BASTION, whose UI requires an open incident.

**Expected:** Active incidents should load for the current session, with a useful empty state when there are none. A server failure should identify whether the problem is authorization, connectivity, or data availability.

**Suggested fix:** Fix the incident list request and add a contract test for the active-run incident query. Keep BASTION available for a clearly selected incident or provide a guided link to create/open one.

### BUG-011 — Control-link, run-status, and threat-status labels disagree (P2)

**Area:** Global status rail and live workspace.

**Reproduction:** Pause the live run, inspect the header and status badges, then navigate between the live workspace and connected sections.

**Observed:** The header showed `CONTROL LINK Live` or `Connected` while the simulator showed `STATUS paused` and a `Resume` control. The control/status area also showed `Normal — no active concerns` while the run’s threat state was `Suspicious — elevated watch`. After the live run surfaced `outcome_resolved`, after-action and replay showed `Run status: running` / `STATUS running`.

**Expected:** Transport connectivity, simulator lifecycle, and threat posture should be separate, consistently named, and derived from the same current run state.

**Suggested fix:** Use distinct labels such as `Realtime: connected`, `Simulation: paused`, `Threat posture: suspicious`, and `Run: terminal`. Centralize status mapping and add visual precedence for terminal state.

### BUG-012 — State-changing and investigation actions are accepted while the simulator is paused without clear semantics (P2)

**Area:** Live command rail.

**Reproduction:** Pause the live simulator, then execute `Watch principal activity`, `Audit token issuance`, and the two `Isolate service` actions.

**Observed:** Actions produced success toasts and Ops feed entries while the simulator remained paused; the control link sometimes flipped to `Live` even though the simulation status stayed paused. The UI did not say whether actions were intentionally allowed against a frozen timeline or whether they were queued.

**Expected:** Paused-mode action semantics should be explicit. If commands execute immediately, the UI should say so and show the command timestamp; if they queue, the UI should show pending state and apply them on resume.

**Suggested fix:** Document and render the execution model in the transport rail; disable controls that are not valid in paused mode; show `executed`, `queued`, or `blocked` in the action result.

### BUG-013 — Terminal-looking live result is not propagated to after-action (P1)

**Area:** `/after-action/run_8024W2GZ4PMQ02P8FXTH840AY6`.

**Reproduction:** Allow the live run to reach the observed header state `STATUS outcome_resolved`, sequence `327`, then click `After-action`.

**Observed:** The page displayed `After-action unavailable` and `HTTP_ERROR: Request failed with status 409`. The intent review said `The intent review unlocks once the run ends.` The dossier and ghost-branch cards both showed `Run status: running`.

**Expected:** A terminal run should unlock its after-action report, intent review, adversary lane, and ghost branch, or clearly explain a short report-generation phase without reporting the run as running.

**Suggested fix:** Make terminal-state persistence and report generation idempotent; have the after-action API return a stable `pending` response only during a named generation phase; update the client from the same terminal event used by the live header.

### BUG-014 — Operator feed loses action type, target detail, and policy outcome (P2)

**Area:** Ops feed.

**Reproduction:** Execute `Isolate service` on Identity Broker and Service Account Vault, then inspect the top feed entries.

**Observed:** The feed showed generic entries such as `EXECUTED ... action.executed` and `OPERATOR ... operator.action.proposed (asset:svc-identity-broker)`. It did not visibly include `Isolate service`, the justification, approval/policy outcome, impact, or a direct link to the affected asset, even though the modal had that information.

**Expected:** A reviewer should be able to audit what action was taken, against which asset, why, with what policy result, and at what time from the feed alone.

**Suggested fix:** Render typed action-feed cards with verb, target name, class, approval state, impact summary, operator justification, and expandable raw event data.

### BUG-015 — Asset inspector can show normal after the run tape has recorded compromise (P1)

**Area:** Live graph/inspector synchronization.

**Reproduction:** While the live run is advancing, select `Identity Broker` around the failed-authentication sequence, then compare the inspector with the run tape and refresh/pause.

**Observed:** The run tape recorded `asset:svc-identity-broker → compromised` at sequence `134`, while the live inspector initially showed `normal`. After pausing and refreshing the state, the inspector showed `compromised`.

**Expected:** The inspector must not expose an older status after a newer authoritative event has been received.

**Suggested fix:** Apply event sequence numbers monotonically, reject stale websocket snapshots, and show a loading/reconciling indicator rather than a misleading status during resync.

### BUG-016 — Hidden-condition events are not explained in the operator UI (P2)

**Area:** Run tape, evidence, and learning flow.

**Reproduction:** Let the Silent Relay run reach sequences `246–250` and inspect the operator-facing timeline/report areas.

**Observed:** The tape contained `sim.hidden_condition.triggered`, `sim.hidden_condition.revealed`, and the customer PII database changing to normal, but no visible explanation, evidence item, or objective connected these events before after-action became unavailable.

**Expected:** A hidden condition may remain hidden until revealed, but once revealed it should be explained in the evidence/timeline and included in the debrief.

**Suggested fix:** Add a user-facing reveal event with cause, affected assets, and learning objective; keep internal event names in diagnostics only.

### BUG-017 — Alert cards remain generic as the incident progresses (P2)

**Area:** Live ALERTS panel.

**Reproduction:** Let the repeated unseen-source alerts and later asset compromises occur, then inspect the right-hand ALERTS panel.

**Observed:** The panel continued to show several generic `Unseen source activity detected` cards without visibly correlating them to the later Identity Broker, Service Account Vault, or Communications Gateway compromise events.

**Expected:** Alerts should preserve their original wording but expose target asset, current status, related sequence range, and whether they have been investigated, superseded, or escalated.

**Suggested fix:** Add alert-to-event correlation, asset labels, severity/status transitions, and a compact “why this matters now” explanation.

### BUG-018 — “Your pattern” metrics are stale or incomplete after the live run resolves (P2)

**Area:** After-action lower panel.

**Reproduction:** Open after-action after the live run has recorded two containment actions and surfaced `outcome_resolved`.

**Observed:** `YOUR PATTERN` showed `6 runs analyzed`, `Score trend 50%`, `Time to first triage 37 evt`, `Containment latency —`, and `Over-containment —` while the current run was treated as running and the containment actions were visible in the Ops feed.

**Expected:** Metrics should either include the current completed run or clearly say `Pending report generation` and explain which metrics are unavailable.

**Suggested fix:** Version metrics by run and report status, show freshness timestamps, and distinguish `not applicable` from `not computed` and `pending`.

### BUG-019 — Terminal replay cursor returns HTTP 400 and no reconstructed graph (P1)

**Area:** `/replay/run_8024W2GZ4PMQ02P8FXTH840AY6`.

**Reproduction:**

1. Open `Replay` for the live run.
2. Click `End` in the read-only replay transport.

**Observed:** The cursor moved to `sequence 500` and the UI showed `500 of 500`, but the top status read `STATUS running`, the provenance line said `Applied: 0–0 (from_events)`, and both the Operational Graph and Historical Inspector showed `Something went wrong` / `Request failed with status 400`. No reconstructed graph or timeline evidence was available.

**Expected:** The replay range should be derived from the run’s actual event stream, and the terminal cursor should reconstruct the last valid state. If no events are available, the UI should say why instead of returning a generic 400.

**Suggested fix:** Clamp the cursor to the persisted event maximum, validate replay requests server-side with a useful error code, and test start/middle/end cursors against a run with action events.

### BUG-020 — Reports route remains empty after the run reaches a terminal-looking state (P1)

**Area:** `/reports`.

**Reproduction:** Open `Reports` after the live header has shown `outcome_resolved`.

**Observed:** The page exposed status `Empty — no data available` and `After-action report not ready`, with copy stating reports are generated after the run completes. This contradicted the live terminal-looking state and the completed containment workflow.

**Expected:** The page should show the generated report, a clearly labeled pending-generation state with progress, or a terminal error with retry/support details.

**Suggested fix:** Subscribe reports to the same terminal event as after-action, make SCRIBE/report generation observable and retryable, and prevent a stale “running” state from hiding a completed result.

### BUG-021 — Admin platform readiness summary contradicts its dependency list (P2)

**Area:** Admin → Platform.

**Reproduction:** Open `/admin` → `Platform`.

**Observed:** The page showed `READINESS ready` and `0/3 dependencies ready`, while the dependency list immediately below showed `postgres ok`, `redis ok`, and `object_storage ok`. It also reported provider `openai-compatible`, local model `Gwimi-4-12B-IT-Q6_K.gguf`, local base URL `http://host.docker.internal:8086/v1`, timeout `200`, and max retries `3`, even though live AI requests failed with provider cancellation.

**Expected:** Readiness should be a single coherent summary. Model-provider readiness should be probed separately from infrastructure dependencies and should reflect whether the configured local provider can answer a health request.

**Suggested fix:** Derive the summary from the same dependency records rendered below it; split `infrastructure ready` from `model ready`; add a non-secret provider health check, last probe time, and failure reason.

### BUG-022 — Replay has no discoverable saved-run entry point from the catalogue (P1)

**Area:** Replay navigation and run persistence UX.

**Reproduction:**

1. Close the original AEGIS tab.
2. Open `http://localhost:3000` again and sign in as `Admin Alpha`.
3. From `/scenarios`, click the `Replay` item in the operations rail.

**Observed:** The Replay item highlighted, but the browser remained on `/scenarios`. The catalogue showed only `Start new run` for Operation Silent Relay and no saved-run selector, resume link, or run ID. The previously observed run was still present when its exact known route was opened directly: `/replay/run_8024W2GZ4PMQ02P8FXTH840AY6`. That route loaded the saved run header and replay controls, and the read-only cursor advanced from sequence `0` to `1`; the graph remained empty at sequence `1`.

**Expected:** Replay should be reachable from the rail without knowing an internal run ID. The page should list saved runs for the current identity, show scenario, run status, date/seed, and provide a clear `Open replay` action. If no run is available, the page should say so rather than silently staying on `/scenarios`.

**Suggested fix:** Give `/replay` its own run-selection state instead of redirecting when no active run is present. Persist and query the current user’s completed runs, expose a resumable/replayable run card in the catalogue, and show the selected run ID in the rail context. Add a regression test that closes/reopens the browser session, signs in again, clicks Replay, and opens the prior Silent Relay run without a copied URL.

### BUG-023 - Switching Copilot roles relabels one in-flight task instead of preserving independent tasks (P1)

**Area:** Copilot role selector and task state.

**Run:** `run_ZBRXME4YXDCCC09MB4AV50K440`.

**Reproduction:**

1. Select TRACE and send a trace prompt while the card shows `TRACE is investigating...` and `Sending...`.
2. Before the request finishes, select ORACLE, then BASTION.
3. Compare the prompt, busy state, and run-tape task events after each role change.

**Observed:** The same TRACE prompt and busy task were displayed as `ORACLE is investigating...` and then `BASTION is investigating...`. The input stayed disabled and there was no visible task ID, cancellation, or separate role history. BASTION's description says it needs an open incident to propose actions, but the selected card still represented the relabelled TRACE investigation.

**Expected:** Each role should have an independent task/session, or switching roles should be disabled until the current request is completed/cancelled. The UI must identify which role owns the in-flight request.

**Suggested fix:** Assign a task ID and role ID to every request, retain per-role history, and provide Cancel/Retry. If role switching intentionally changes the active view, keep the request owner and status visible instead of changing the task's identity.

### BUG-024 - Agent task failures do not consistently resolve the Copilot UI (P1)

**Area:** Connected AI model integration and Copilot lifecycle.

**Run:** `run_ZBRXME4YXDCCC09MB4AV50K440`; provider configured at port `8086`.

**Reproduction:** Send independent investigation prompts to WATCHTOWER and TRACE, then attempt ORACLE and BASTION while the live run is active. Wait for the provider response and inspect both the Copilot card and the run tape.

**Observed:** WATCHTOWER eventually displayed `Provider request was cancelled (PROVIDER_FAILURE)`. TRACE, ORACLE, and BASTION produced `agent.task.failed` events in the run tape, but the selected Copilot card could remain `investigating...` or `Sending...`, and later showed `signal timed out` without a clear retry/cancel path or reliable input reset. No usable model answer was returned from any role.

**Expected:** The client must consume the authoritative task transition and render `queued -> working -> succeeded/partial/failed/cancelled` consistently. A failure should include a useful error, request/task ID, retry action, and re-enabled input.

**Suggested fix:** Make task completion/failure events idempotently update the role card, add a bounded timeout with explicit cancellation, and expose provider health plus retry state. Do not leave a role in a busy state after its backend task has failed.

### BUG-025 - A paused run cannot be resumed after an AI/task failure (P1)

**Area:** Simulator lifecycle controls.

**Run:** `run_ZBRXME4YXDCCC09MB4AV50K440`.

**Reproduction:**

1. Let the run pause after the AI task failures and containment actions.
2. Confirm the header shows `STATUS paused`, `Simulation paused`, and `SEQ 318`.
3. Click `Resume sim`; then try `Resync`, reload the persisted run URL, click Resume again, and wait about 10 seconds.
4. Use `Step` while paused and inspect the sequence/time changes.

**Observed:** Resume became disabled without advancing the simulation or changing sequence `318`. Resync or reload could make Resume appear enabled again, but the next click reproduced the same no-progress state. Waiting did not advance the run. Step generated agent-session/task events, including a later `agent.task.failed`, rather than advancing simulation time. The control link also alternated between `Live` and `Sim paused` while the run status stayed paused.

**Expected:** Resume should either advance the simulator or return a visible, actionable failure with retry/cancel guidance. A task/provider failure must not strand the run in a non-terminal paused state.

**Suggested fix:** Separate simulator lifecycle from AI task lifecycle, make pause/resume requests idempotent, clear or cancel pending task state during recovery, and show a durable error state when the simulator cannot resume. Add an end-to-end test for provider timeout -> pause -> resume.

### BUG-026 - Incident-queue failure blocks the BASTION workflow with no actionable fallback (P1)

**Area:** Incidents, Copilot orchestration, and containment workflow.

**Run:** `run_ZBRXME4YXDCCC09MB4AV50K440`.

**Reproduction:** Open `/incidents` from the run rail while the run is active, then select BASTION in Copilot.

**Observed:** `/incidents` rendered `Status: Error - operation failed`, `Unable to load incidents.`, and only a Retry control. BASTION's card states `needs an open incident to propose actions`; because the incident queue cannot load, there is no way to create/select the required incident or understand whether the AI task is blocked versus failing at the provider.

**Expected:** The incident queue should load, or BASTION should provide a clear create/open-incident fallback and a distinct blocked state with the missing prerequisite.

**Suggested fix:** Make incident retrieval/retry reliable, surface the incident ID and run association, and gate BASTION with an explicit `Incident required` state that links to incident creation or selection. Do not send an indistinguishable provider request when the prerequisite is unavailable.

## Final-pass connected-section evidence

The following checks were performed against `run_ZBRXME4YXDCCC09MB4AV50K440` after the second playthrough attempt:

| Section | Exact result |
|---|---|
| Active run | Rail navigation returned to `/scenarios`; it did not preserve the current run URL. |
| Incidents | `/incidents` showed `Unable to load incidents.` with `Status: Error - operation failed`. |
| Replay | `/replay/run_ZBRXME4YXDCCC09MB4AV50K440` loaded with range `0-500`; End moved to `500 of 500`, then the graph and inspector returned `HTTP_ERROR`, `Request failed with status 400`, and `Applied: 0-0 (from_events)`. Cinematic replay showed `CINEMATIC_REPLAY_UNAVAILABLE`. |
| After-action | `/after-action/run_ZBRXME4YXDCCC09MB4AV50K440` eventually returned `HTTP_ERROR: Request failed with status 409`, `After-action unavailable`, and `Run status: paused`. |
| Reports | `/reports` showed `Empty - no data available` and `After-action report not ready`, which left no debrief path for the blocked run. |

The prior user-provided screenshots remain useful evidence for the first run's same symptoms:

- Replay failure: `C:/Users/ytrjx/AppData/Local/Temp/codex-clipboard-b34fbdba-1d5d-4233-b62f-f5158ab7d7f9.png`
- Reports empty: `C:/Users/ytrjx/AppData/Local/Temp/codex-clipboard-f791e644-6ebe-4ab7-8086-a6e74c0edb90.png`

## Connected-section results

| Section | URL/result | QA result |
|---|---|---|
| Scenarios | `/scenarios` | Loaded; tutorial and Silent Relay cards were available. First-run context and run ownership issues remain (BUG-001, BUG-002). |
| Active run | Rail link routed to `/scenarios` | Failed; current run context was lost (BUG-009). |
| Incidents | `/incidents` | Failed with `Unable to load incidents.` (BUG-010). |
| Replay | `/replay/run_8024W2GZ4PMQ02P8FXTH840AY6` | Route loaded, but terminal cursor reconstruction returned HTTP 400 (BUG-019). |
| After-action | `/after-action/run_8024W2GZ4PMQ02P8FXTH840AY6` | HTTP 409, unavailable, and incorrectly showed `Run status: running` (BUG-013). |
| Reports | `/reports` | Empty/report not ready despite terminal-looking live state (BUG-020). |
| Admin | `/admin` | Loaded. Users & Roles and Policy were readable; Platform displayed contradictory readiness (BUG-021). |
| Design system | Design System page | Loaded outside operational context. Tokens, component playground, status catalogue, and replay shortcuts were visible. No additional functional defect was recorded from this smoke inspection. |

## AI verification

The connected model was deliberately exercised during the live simulation rather than treated as a static configuration check.

- WATCHTOWER received a live-alert/telemetry investigation prompt with requested sequence citations.
- TRACE received a targeted trace prompt covering sequences `14`, `27`, `51`, and `72`.
- Both requests entered `Working…`, then failed with `PROVIDER_FAILURE` / `Provider request was cancelled` and produced `agent.task.failed` entries.
- In the first run, BASTION could not be tested because it requires an open incident and `/incidents` failed to load.
- In the final-pass rerun, all four roles were explicitly attempted. WATCHTOWER surfaced `PROVIDER_FAILURE`; TRACE, ORACLE, and BASTION emitted `agent.task.failed` events, but their Copilot cards did not consistently resolve to a failure state. No role returned a usable model answer.
- BASTION remained blocked by the unavailable incident queue, so its required open-incident workflow could not be exercised end to end.
- The Admin platform view confirms a local model configuration pointing to port `8086`, but the UI does not expose a successful provider health result.

## Concise UI/UX recommendations

1. **Make state authoritative and composable.** Render separate chips for realtime connection, simulator lifecycle, threat posture, and terminal/report status. Drive all routes from one versioned run state.
2. **Turn tutorial objectives into real gates.** Show objective status, disable Next for required unmet objectives, and provide an explicit skip with a recorded reason.
3. **Add a reliable action audit surface.** Display action verb, asset name, class, approval state, impact, operator reason, timestamp, and resulting asset state in the feed.
4. **Give AI tasks a complete lifecycle.** Use `queued → working → succeeded/partial/failed/cancelled`, expose timeout and retry, and show provider health and request IDs without exposing secrets.
5. **Make report generation observable.** A terminal run should immediately show a pending report state with progress and a retry path, not a generic 409/empty state.
6. **Correlate alerts with the graph and timeline.** Add asset names, sequence ranges, status transitions, and “investigated/escalated/contained” markers.
7. **Make navigation run-aware.** `Active run`, Replay, After-action, and Reports should preserve the current run ID and show a clear no-active-run state when none exists.
8. **Keep paused-mode semantics explicit.** Tell the operator whether actions execute immediately, queue, or are blocked while simulation time is paused.
9. **Separate catalogue/demo onboarding from operational onboarding.** Start a fresh training run before teaching controls, and label stopped demo data as inert.
10. **Add end-to-end smoke coverage.** A single automated scenario should verify: create run → tutorial objective → alert → incident → AI task → approved containment → terminal event → replay → report.

## Evidence and limitations

- Browser screenshots were inspected live through Computer Use; no additional screenshot files were created so the requested artifact remains Markdown-only.
- Exact routes, run IDs, sequence numbers, and UI/API error text are recorded above for reproduction.
- BUG-001 and BUG-003 are explicitly marked as supplementary observations captured before the Computer Use runtime repair in the earlier QA session; they were not silently treated as final-pass Computer Use interactions.
- The final pass made no application-source changes, configuration changes, runbook changes, or data edits beyond the normal in-app actions required to play the tutorial and simulation.
