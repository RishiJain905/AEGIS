# Cockpit Rework QA Record — 2026-08-02

**Pass:** full-flow browser QA of the "One stage, no walls" cockpit (phases 1–5) plus held-over
functional checks, on the rebuilt Docker stack at `localhost:3000`.
**Driver:** Playwright MCP at 1440×900 (claude-in-chrome extension unavailable).
**Runs:** `run_3AWSFEDHQG6P6JTEJ0J72XYCT3` (cockpit + replay/after-action),
`run_H07BV206SHJS7HH13M51WAEVG7` (observe/isolate), `run_E02AHM3GRDCYE9CDMM1PBTD3D1` (tutorial).
**Screenshots:** 15 (`qa-01`…`qa-15`) in the session scratchpad
(`…\a61b2cfa-45fc-4c02-8d0d-c4b2f1a7b181\scratchpad\`).

**Verdict at the time:** cockpit structure ready; four functional blockers underneath it.
This record tracks what was verified so later passes (Codex Luna A–Z playthrough) need not
re-prove the passed items — only the blockers' fixes and anything new.

## Verified PASS (do not need re-proving, spot-checks only)

| # | Check | Evidence |
|---|---|---|
| A1 | Full-bleed stage, fused console, no docks, no Focus-graph | testids present; dock text absent |
| A2 | Node select → inspector sheet, camera nudge, stage-click deselect | (minor: subject line showed raw id — fix shipped in polish wave) |
| A3 | Signals stack: top-right, exactly 40vh, internal scroll, capsule, `A` toggles | measured 360px = 40vh |
| A4 | Signals×sheet collision rule | capsule docks at sheet top edge (y 142.5 vs 130.5); overlay within sheet bounds; Esc ordering correct |
| A6 | Dual-sheet space budget | 480→366 each, centre 412px = exactly 36.0% |
| A7 | Chronicle: chevron + `T`; tick-probe pinning + Follow live preserved | pinned at 00:00:18 SEQ 7; unpinned to live |
| A8 | Console = one Tab stop with roving arrows across all clusters incl. tape beats | |
| A9 | <1280 stacked flow with sticky console | (overflow at 1100px — fix shipped in polish wave) |
| A10 | Light theme + reduced-motion (verified via media emulation, durations → 1e-05s) | |
| A11 | Pause/stop semantics: frozen-timeline ribbon, run-ended ribbon, command gating, rail truthful through terminal | SEQ frozen while paused |
| A12 | Tutorial prose rewrite real; objective gating works | no beat narrates docks/tabs |
| B13a | Observe: pending chip → durable "Under observation"; compromise not erased; run advances | appliedControls `["observed"]` |
| B14 | Alert ×N collapse per asset with SEQ ranges; distinct assets stay separate | ×3 cards |
| B17 | Incidents auto-open from alerts; incident context in inspector | `incident.created` follows `alert.created` |
| B18 | After-action + reports load; newest-run selection; deterministic fallback labeled | score 54.4/100 F with provenance |

## Blockers found (all now fixed in the Aug-4/5 wave — LUNA MUST RE-VERIFY)

1. **Copilot never answered** (0 completed tasks ever; model-invented evidence ids;
   orphaned running tasks) → fixed by grounding repair loop + prevention + stale-task sweep
   (`fix-grounding2`).
2. **Executed posture never reached the live board** (Resync fixed it instantly) → root cause:
   graph store rejected sparse-channel deltas as gaps; plus the WebSocket gateway killed 94% of
   connections via backfill overflow closing sockets → both fixed (`fix-live-board2`).
3. **Toast occluded the console corner**, blocking Isolate/All actions/chronicle/copilot chip →
   rehomed with auto-dismiss (`cockpit-polish`).
4. **Replay served 12 stub nodes / 0 edges** despite perfect snapshots → root cause: the
   projector's only topology source was an event no producer ever emitted; now seeds from the
   run's earliest graph snapshot (`fix-replay-read2`); stale archives self-heal via projector
   version bump.

## Secondary findings (fixed in the same wave unless noted)

- Incident/action events carried wall-clock in `simTime` (chronicle interleaving, CLOCK flip) — `fix-grounding2`.
- Type-to-compose seeded without focusing the composer; I/C/T/A unreachable from console; focus
  not restored on close from signals-stack invokers — `cockpit-polish`.
- 2D→3D→2D board corruption (owner-reported Aug 4): overlay canvases missing CSS box at
  dpr 0.9 (90% zoom) + settled layout discarded on remount — `fix-graph-toggle`, live-verified
  pixel-identical round trips.
- Signals capsule overlapped graph zoom controls (owner screenshot) — `cockpit-polish`.
- Chronicle rows showed raw event strings; duplicate CAUSE REVEALED cards; live inspector fired
  after-action 404 — `cockpit-polish`.
- Pydantic `stream_message_id` serializer warnings — `fix-grounding2` (if quick).

## Open by decision (backlog, not defects in flight)

Chronicle phase 6 (tick alignment + leader lines) — owner decides after flying the cockpit.
Realtime follow-ups: server-side paused-subscription self-heal, terminated-run subscriptions,
health-chip vs banner sync, plan_recovery distance cap. Snapshot-worker per-run exception
isolation. `aegis_replay` mypy gate. Unclustered-node layout constraint one-liner.

## Luna partial playthrough — 2026-08-05 (Playwright-driven, ended early by owner)

### Scope and interim verdict

This is a partial independent playthrough, stopped at the owner's request before the full
A–Z script was complete. No application code, configuration, container, or database
fixtures were changed by this evaluation. The native `@computer-use` broker was unavailable
on this machine (`Computer Use native pipe is unavailable`), so the same headed Chrome
session was driven through Playwright as a documented fallback.

Interim verdict: **not ready for final sign-off**. The cockpit and the live-board/replay
fixes were materially improved and several important visual behaviours passed in real play,
but AI evidence grounding is still inconsistent and the after-action report omitted a
decision that was plainly present in the Chronicle.

### A–Z coverage reached

Times below are approximate local Toronto wall-clock times where noted; simulation times and
sequence numbers are taken from the UI.

1. **Setup and tutorial — covered.** Signed in as Admin Alpha from `/sign-in` on the fresh
   operator state. Started Tutorial run `run_E02AHM3GRDCYE9CDMM1PBTD3D1` (seed `1000`).
   Played chapters 1–3 seriously. Chapter 2 correctly gated Next until an asset was selected
   and View options was opened. Chapter 3 correctly gated Next until Explanation was opened;
   the incident objective was optional and visibly skippable, but I opened the incident from
   the inspector instead. The tutorial later held at its 25-minute horizon and I ended the
   walkthrough honestly after chapter 3. Chapters 4+ and a complete tutorial were not
   covered.

2. **Live Operation Silent Relay — covered across four Admin Alpha runs.** The deliberately
   selected loadout for the main runs was Investigate RoE with Bias guard and Threat tempo:
   it preserves investigative flexibility while making evidence quality and escalation
   pressure visible. The commander intent was consistently to protect student records,
   preserve evidence, and isolate only confirmed compromise.

   - `run_XVJ33CJW7KBJ7ZBJM8WBNY7ED7`, seed `957885134` (approximately 00:02 local):
     loaded the full-bleed 38-node cockpit at 1440×900. I followed the Identity Broker
     alert, saw the graph focus and Inspector sheet arrive, opened Chronicle, and ran a real
     WATCHTOWER triage prompt. I did not execute an action; the run reached its 25-minute
     horizon. Evidence search for `asset:svc-sso-broker` did return authentication telemetry
     and alert-created records.

   - `run_T2AGFNQA2JXYNQ6842NWHYTTB3`, seed `643659782`: reached a compromised Identity
     Broker and opened the Class 2 Isolate service consequence gate. The gate clearly showed
     network severance, dependent-service impact, reversibility, and an audited justification
     field. I filled a real justification but accidentally clicked Stand down instead of the
     disabled-until-filled Confirm control; this was operator error, not an application
     defect. No isolation was executed and the run ended around sim 00:06:15.

   - `run_8T5DRS27ZQDVFNMDH0G1GWRNK0`, seed `345715149`: executed Observe on SSO Broker.
     The Inspector retained the threat posture and showed a durable `Under observation`
     control; the board updated live without pressing Resync and the run advanced. This seed
     did not produce a confirmed compromise, so isolation was not available. I also paused
     and resumed, verified 2D→3D→2D while paused, checked both themes, and resized to 1100×800
     to exercise the stacked layout. The run reached 25:00 and produced a report.

   - `run_853DCS5KJ47N8CW2GWMSDE4347`, seed `1242420710`: used Forward-deployed RoE with the
     same two loadout caps. Identity Broker became compromised at SEQ107. I opened the
     consequence gate and executed Isolate with this justification: “Confirmed compromise on
     Identity Broker at SEQ 107, corroborated by the unseen-source alert and failed-auth
     telemetry; isolate now to protect student records and preserve the evidence trail.”
     The Inspector reached `contained` with durable `Isolated`, the graph stayed synced, and
     the run advanced from sim 00:06:00/SEQ269 to 00:06:15/SEQ288 after the action. Chronicle
     contained exactly one executed Isolate row at sim 00:05:40 with the justification.

3. **Investigate / AI / act — partially covered.** Alert-to-asset focus, Inspector arrival,
   Chronicle, Evidence search, Observe, and one real Isolate were covered. WATCHTOWER was
   exercised with a real triage prompt. I closed the copilot during the turn and saw the
   chip change from working to a `1 unread replies` state with a preview, then reopened the
   answer. TRACE follow-up and a full BASTION attempt were not reached before the owner stop.
   I did not pin a hypothesis.

4. **Incidents — partially covered.** Alerts auto-opened incident context. The fourth run
   showed `Confirmed compromise on asset:svc-identity-broker` in the Inspector and the
   action appeared in Chronicle. I did not complete a BASTION case interaction.

5. **Outcome / exploration — partially covered.** Two runs reached their normal 25-minute
   horizon and two action-oriented seeds ended at about 00:06:15. Evidence was searched and
   the Evidence/Hypotheses surface was inspected, but the full eight-minute outcome path,
   complete hypothesis workflow, and all exploratory branches were not completed.

6. **After-action, reports, replay — partially covered.** The fourth run's after-action
   report loaded without an error and scored `46.7 / 100`, grade F, with provenance and an
   honest explanation of missed true-cause signals. The report omitted the executed decision
   from `Timeline & decisions`, however. The replay was opened from the run picker and scrubbed
   to End: sequence `290 of 290`, `38 nodes · LOD detail`, provenance
   `from_snapshot_plus_events`, with real edges present. The Reports page was not separately
   covered.

7. **Second identity — not covered.** I did not sign out Admin Alpha and test Operator Alpha
   access or start the second identity's tutorial before the owner stopped the playthrough.

### Verification of the four fixed blockers

1. **Copilot grounding repair — PARTIAL FAIL.** On
   `run_XVJ33CJW7KBJ7ZBJM8WBNY7ED7`, WATCHTOWER was sent:
   “Triage the newest unseen-source alerts. Which asset should I investigate first, what
   evidence ids support that priority, and what should I verify before isolating anything?”
   The first task emitted `Sequence 325 · agent.task.failed`, then a retry emitted
   `Sequence 329 · agent.task.started`; after roughly 105 seconds the task completed and did
   not remain an eternal spinner. The answer cited the real alert ID
   `alert:det-fea68dcd484a5db57250` and the real asset
   `asset:svc-sso-broker`, but said: “The AEGIS evidence catalogue contains zero items, so no
   evidence IDs support this prioritization.” That is inconsistent with the Evidence tab,
   where searching `asset:svc-sso-broker` displayed authentication successes, failed
   authentication events, and `alert.created` records, including the same alert ID in the
   payload. The completion loop and anti-invention behaviour are improved, but the required
   real, grounded evidence-ID answer is not verified and should be treated as a blocker.
   Task id: `atk_Y6T52527B54QJD6GBPBTJ0WM3T`; trace:
   `trc_FSV9X6GCA9ERS79D5RXM8BJAEJ`.

2. **Live executed posture — PASS with a transient consistency nit.** On
   `run_853DCS5KJ47N8CW2GWMSDE4347`, after the confirmed Isolate execution, the Inspector
   showed `contained` and `Isolated`, the graph reported `Graph synced`, and the event tape
   recorded `Sequence 252 · Asset asset:svc-identity-broker → isolated`. The run continued
   advancing and the action was visible in Chronicle without Resync. Observe on
   `run_8T5DRS27ZQDVFNMDH0G1GWRNK0` also updated live and retained the durable observation
   state. During the fourth run there was a brief Inspector/command-bar mismatch: the
   Inspector already showed Identity Broker `compromised` while the console action bar
   momentarily displayed Normal; it corrected before/after execution.

3. **Console action-result rail / toast placement — PASS in the checked sizes.** At 1440×900,
   the Observe result appeared in the console band as `Action executed` / `Observe on SSO
   Broker`; the action controls, Chronicle, copilot chip, and console corner remained usable.
   The Isolate run likewise kept its result and controls inside the console band. At 1100×800
   the layout stacked rather than covering controls. No action-result rail occluded a button in
   the observed view.

4. **Replay topology — PASS.** From the replay picker, I opened
   `run_853DCS5KJ47N8CW2GWMSDE4347`, pressed End, and verified `290 of 290` with
   `from_snapshot_plus_events`. The replay surface reported `38 nodes · LOD detail` and
   displayed real topology edges; it did not regress to the prior 12-node/0-edge stub graph.

### Visual confirmations obtained

- **(a) Action-result rail:** PASS. `qa-live-observe-1440.png` shows the 1440×900 graph,
  Inspector, and console band with the controls unobscured; the corresponding live snapshot
  contained the attributed `Action executed` Observe result. `qa-fourth-isolate.png` shows the
  post-Isolate console band and Inspector with `contained`/`Isolated`, without the rail covering
  an action button.

- **(b) SIGNALS clearance:** PASS. At 1440×900 the SIGNALS capsule/stack sits top-right and
  clears the graph search, View options, Fit/zoom, and Reset row. At 1100×800 the layout stacks
  SIGNALS below the console; after scrolling, the wrapped graph-control row remained clear and
  usable. Evidence images: `qa-2d-paused-before.png`, `qa-third-dark-1440.png`,
  `qa-third-1100.png`, and `qa-third-1100-scroll.png`.

- **(c) Closed-sheet copilot answer:** PASS. With WATCHTOWER running, the closed chip showed
  `Copilot — WATCHTOWER working`. When the answer landed while closed it became
  `Copilot — 1 unread replies` and showed a preview beginning
  `WATCHTOWER: The newest unseen-source alert is alert:det-fea68dcd484a5db57250 on
  asset:svc-sso-broker...` before reopening the sheet.

### Defects found

#### P1 — Copilot evidence catalogue disagrees with the Evidence surface

**Repro:** As Admin Alpha, start `run_XVJ33CJW7KBJ7ZBJM8WBNY7ED7`; open Copilot and send
the WATCHTOWER prompt quoted above. Wait for the failed attempt and retry to settle. Open
Evidence and search `asset:svc-sso-broker`. The copilot answer claims zero evidence items and
provides no evidence IDs, while Evidence shows authentication and alert-created records for
that asset. The answer does cite a valid alert ID, so this is not a wholly invented answer; it
is an incomplete and internally contradictory grounding result. This directly violates the
critical requirement that an AI teammate return actionable answers with valid evidence IDs.

#### P1 — After-action `Timeline & decisions` drops the executed isolation

**Repro:** As Admin Alpha, start `run_853DCS5KJ47N8CW2GWMSDE4347`; select the Identity Broker
compromise; choose Isolate service; enter the exact justification recorded above; confirm
execution. Chronicle shows one executed Isolate row at sim 00:05:40, plus
`Sequence 252 · Asset asset:svc-identity-broker → isolated`, and the Inspector shows
`contained`/`Isolated`. Navigate to After-action. The report loads and scores `46.7 / 100`
but `Timeline & decisions` says `0` and `No recorded decisions.` The debrief therefore fails
to teach the operator from the most consequential decision in the run.

#### P2 — Short-lived live status mismatch between Inspector and command bar

**Repro:** In `run_853DCS5KJ47N8CW2GWMSDE4347`, click the Identity Broker compromised alert as
the event arrives. The Inspector showed `Asset status compromised` while the console action
bar briefly rendered `Normal`. The command bar corrected after the live projection caught up,
and the action itself used the correct compromised state. This is a visible synchronization
race, not a permanent posture failure, but it can make an operator hesitate at the exact
moment they must decide whether to isolate.

#### P2 — Header debrief state can lag report generation

**Repro:** At the end of `run_853DCS5KJ47N8CW2GWMSDE4347`, the live cockpit still showed
`DEBRIEF PENDING` while the event tape already contained report-generation completion
(`Sequence 288`). Navigating to After-action refreshed the state to `Report ready`. This was
recoverable without a reload, but it weakens confidence in the run's final state.

#### P2 — Copilot first attempt visibly fails before recovery

**Repro:** The WATCHTOWER task above showed `agent.task.failed` at SEQ325 before a retry at
SEQ329 eventually completed. The only retained user-facing failure wording was the generic
`An agent could not finish its task`; no precise cause was exposed in the playthrough. The
retry prevents a dead end, but an operator needs a clear, attributable retry/error state when
the local model is slow or fails.

### UX observations, ranked by impact

1. **Trust is the highest-impact issue.** The cockpit's visual grounding is strong, but an AI
   teammate saying the evidence catalogue is empty while the Evidence tab contains records is
   more damaging than a normal UI defect. Operators cannot safely act on a triage answer until
   its IDs and the Evidence surface agree.

2. **The after-action is useful but currently incomplete.** The score, hidden-cause reveal,
   provenance, missed signals, and honest F grade were valuable. Omitting the executed Isolate
   from the decision timeline makes the debrief contradict the run's central story.

3. **The cockpit flow is otherwise coherent.** Graph → SIGNALS → Inspector → console is easy
   to follow. Clicking an alert asset focuses the graph and summons the Inspector. Chronicle
   makes event order and sim time spatially legible, and the consequence gate makes impact,
   reversibility, and justification explicit.

4. **Tutorial gating is effective.** The first-time path prevented skipping the required
   selection, View options, and Explanation beats while allowing the optional incident
   objective to be skipped. The partial run did not establish whether the later chapters stay
   equally disciplined.

5. **Responsive and theme behaviour held up.** The full-bleed graph remained readable in both
   light and dark themes. The 2D→3D→2D round trip while paused returned to the same visible
   topology and controls. The 1100px stacked layout kept the graph controls and console actions
   usable.

6. **The local-model pacing needs operator-aware affordances.** A slow turn can span much of a
   short seeded run, and the generic failure/retry card gives little information. The working
   chip and closed-sheet unread preview are excellent mitigations, but a visible remaining-run
   horizon or queued-task indicator would help operators decide whether to wait or act.

### What I would change first

1. Make the copilot's evidence retrieval and the Evidence tab consume the same run-scoped
   catalogue, validate every cited ID before completion, and fail explicitly when no valid
   evidence exists instead of returning a contradictory “zero items” answer.
2. Project Chronicle action decisions, consequences, and justifications into the after-action
   `Timeline & decisions` section, with an end-to-end assertion that every executed action
   appears exactly once.
3. Unify the Inspector, command-bar, and header status projection so a single live version is
   used for posture and report readiness; eliminate the observed transient mismatches.
4. Preserve the generic retry recovery, but expose the task failure reason and retry state in
   the copilot card so a slow local model does not look like an unexplained failure.

### Evidence artifacts captured

The Playwright session captured these representative screenshots under `.playwright-cli/`:

- `qa-live-observe-1440.png` — full-bleed cockpit, live Observe result, unobscured console.
- `qa-fourth-isolate.png` — post-Isolate live Inspector/console state and 38-node graph.
- `qa-2d-paused-before.png`, `qa-2d-paused-after.png` — paused 2D round-trip comparison.
- `qa-third-dark-1440.png` — dark-theme cockpit.
- `qa-third-1100.png`, `qa-third-1100-scroll.png` — stacked responsive layout and cleared
  controls after scroll.
- `qa-replay-end.png` — replay transport at End; the accompanying page state reported the
  real 38-node, edge-bearing topology.

### Explicitly not covered before the owner stop

TRACE follow-up, BASTION execution, hypothesis pinning, a separately verified Reports page,
the full outcome/debrief loop for every seed, Admin Alpha sign-out, Operator Alpha policy
isolation, and Operator Alpha's own tutorial start. No conclusion is drawn for those paths.
