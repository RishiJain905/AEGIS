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

## Owner-reported defects — 2026-08-07

Reported directly by the owner from live play (screenshots on file), logged verbatim for the
next fix wave. Not yet independently reproduced.

- **P1 — No way to restart after Stop.** After pressing Stop, the run enters
  `STOPPED` / `RUN ENDED — the timeline is read-only; commands can no longer execute`, and the
  cockpit offers no restart control at all. Observed on `run_N9YES8EF6XG8SANKEANCT0DSE7`, seed
  `1620701892`, stopped at SEQ 17. The owner wants a restart button/option (relaunch same
  scenario+seed, or a clear path back to a fresh launch) instead of a dead end.
- **P1 — Node command bar buttons unclickable except Deep dive.** After clicking a node (2D or
  3D alike), the inspector command bar's `Observe` / `Increase telemetry` / `Isolate service` /
  `All actions` buttons do not respond to clicks; only `Deep dive` responds — and the owner
  flags Deep dive's behaviour as buggy too. Owner screenshot shows the bar on Kubernetes
  Control Plane (`normal` posture). **Repro note for the fix agent:** the accompanying
  screenshot's run is in the ended state, where command gating is designed to disable
  state-changing actions — first verify whether the dead buttons reproduce on a *live* run
  (defect in command dispatch) or only on ended runs (defect is the gating being invisible:
  buttons render enabled-looking and give no feedback about why clicks are ignored). Either
  way the current behaviour reads as broken to the operator and needs fixing.

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

## Luna full playthrough — 2026-08-06

### Driver

Primary driver: visible computer-use via `@oai/sky`. It worked for the end-to-end playthrough,
including sign-in, tutorial, live operations, actions, reports, replay, identity switching, and
the responsive/theme checks. During a final read-only replay lookup, computer-use stopped with
the runtime error that it could not determine the current browser URL with enough confidence.
I then used the Playwright CLI only to confirm replay metadata and pin the tutorial event
sequence. This fallback was explicit; Playwright was not used for gameplay before that error.

### Previously-fixed blocker spot-checks

- Live graph delta/backfill without Resync: PASS. Observe and Isolate changed the Inspector,
  graph focus, posture, and Chronicle while Resync remained untouched.
- Toast occlusion: PASS. Action toasts did not cover the console controls at the 1200px check.
- Replay topology seed: PASS. Start, middle, and End reconstructed the real 38-node graph with
  edges; the 2D -> 3D -> 2D round trip retained the topology.
- Copilot grounding repair loop: REGRESSED. Working, failure, retry, and completion states were
  visible, but completed answers still claimed an empty evidence catalogue when Evidence had
  records. See the known P1 below.

### Coverage checklist

1. **Tutorial: PARTIAL / BLOCKED.** Admin Alpha completed all 10 chapters in
   `run_E02AHM3GRDCYE9CDMM1PBTD3D1`, seed `1000`, through the clean terminal at sim
   `00:25:00Z`, SEQ `412`. Early gating taught selection, graph controls, explanation, and
   incident context well. The required Observe beat in chapter 4 would not advance after a
   successful Observe; the final screen reported four skipped or unmet objectives. The tutorial
   is therefore not completable through the intended path.
2. **Silent Relay: PASS for the live board, NOT READY overall.** I deliberately used Bias guard
   and Threat tempo. The main investigation used Forward-deployed ROE with intent to protect
   student records, preserve evidence, and require approval for state changes. Alerts named
   SSO Broker, clicking the asset focused the graph and opened Inspector, SIGNALS exposed cause
   reveals, and Chronicle preserved event order and justification. A second run used Observe ROE
   to test the unattended path; a third used Forward-deployed ROE and early containment.
3. **Actions: PASS with a visible race.** In
   `run_1QGA6JBQP0XHVTVETRFRSQT2S0`, seed `1327565196`, Observe executed at SEQ `423` and
   Class 2 Isolate service executed at SEQ `428` after the audited justification was entered.
   The modal showed class, target, reversibility, severed/dependent-service consequences, and
   Stand down versus Confirm. Inspector and graph state persisted without Resync. Immediately
   after confirmation, Inspector showed `contained`/`Isolated` while the command bar briefly
   still showed `normal`.
4. **Simulation integrity: PASS for termination, with an opaque live horizon.** Tutorial pause
   and resume worked and reached sim `00:25:00Z` / SEQ `412`. Silent Relay consistently reached
   a fixed-looking terminal boundary at sim `00:06:15Z`: the unattended
   `run_V3B7K2HC4JYJ39WQHSNNH8P0C5`, seed `1427798730`, stopped at SEQ `284`; the controlled
   `run_FY3RA94A9DBY3QWC38HMFTMRM3`, seed `872356573`, stopped at SEQ `297` after Observe at
   SEQ `110` and Isolate at SEQ `183`. Both ended read-only with an outcome and generated a
   report; there was no eternal spinner or dead run. The 6:15 live horizon is not labelled in
   the cockpit and is much shorter than the tutorial horizon.
5. **After-action, Reports, and replay: MIXED.** The first live run produced an after-action
   score of `52.7 / 100` (F), hidden cause `Compromised service account credentials`, and a
   separate immutable Reports v1. Replay scrubbed Start / middle / End with real topology and
   the 3D round trip worked. The after-action Timeline & decisions omitted the executed Isolate;
   the Reports page also reported zero evidence, proposals, policy decisions, and no agent
   investigation artifacts despite the run having a completed copilot task and Chronicle
   agent events.
6. **Identity isolation: BLOCKED.** After signing out Admin Alpha and signing in Operator
   Alpha, the role and navigation policy differed as expected. Starting the tutorial did not
   create an Operator-owned run: the catalogue returned an error that the deterministic seed
   run already belonged to another operator and only its owner or an administrator could
   restart it. Operator Alpha could not briefly start the requested tutorial path.
7. **Spot checks: PASS / USABLE.** Dark and light themes were readable. At a visible 1200px
   window (below 1280px), the cockpit remained operable but the graph, Inspector, Signals, and
   console were cramped. Replay 2D -> 3D -> 2D returned to the same real topology.

### AI teammate emphasis

- **WATCHTOWER triage:** Tutorial WATCHTOWER and the live WATCHTOWER both completed after the
  local-model delay. In the live run, the first attempt failed at SEQ `432`, then the retry
  completed at SEQ `437`. The answer said there were no evidence items and did not provide the
  requested exact evidence IDs or two concrete next actions. Evidence search for `auth` in the
  same run returned real `telemetry.authentication.succeeded` and `alert.created` records.
  This is a direct contradiction, not an invented-ID problem: the answer cited no usable IDs.
- **TRACE follow-up:** TRACE was reachable and started against the identity asset at SEQ `440`.
  Its first task failed at SEQ `441` with provider JSON truncation. A bounded retry started at
  SEQ `442` but produced no answer before the run stopped. There was no answer whose evidence
  IDs could be validated.
- **BASTION / proposal path:** BASTION was reachable. Its prompt requested a proportional
  containment proposal with class, consequences, evidence preservation, and an explicit gate.
  The task failed at SEQ `448` and never surfaced a proposal. No agent executed a state change
  directly. The manual Class 2 gate did enforce operator approval correctly, but the agent
  proposal/approve flow itself was not reached.
- **Lifecycle honesty:** Working cards, attributed failures, retry/tool activity, and completion
  were visible for WATCHTOWER. TRACE and BASTION exposed failure states, but BASTION remained
  visually `Working`/spinning after the run stopped. The prior closed-sheet unread PASS was
  spot-checked from the earlier run; in this pass the sheet was closed after the WATCHTOWER
  answer, but no clear new unread badge appeared before the later run stop.
- **Learning value:** The agent sometimes teaches the right triage structure - identify the
  urgent asset, state uncertainty, request risk, and propose next steps. It is not trustworthy
  as a blue-team teacher while it says the evidence catalogue is empty in the presence of
  records and returns no IDs. A student could learn the vocabulary but would learn an unsafe
  evidence workflow and would not receive an actionable triage answer.

### Known defects rechecked

- **P1 copilot evidence catalogue says zero while Evidence has records:** STILL PRESENT. In
  `run_1QGA6JBQP0XHVTVETRFRSQT2S0`, seed `1327565196`, sim `00:10:08Z`, the completed answer at
  SEQ `437` said the catalogue was empty while the Evidence tab contained authentication and
  alert-created records.
- **P1 after-action Timeline & decisions drops the executed isolate:** STILL PRESENT. In the
  same run, Isolate executed at sim `00:10:08Z` / SEQ `428` and appeared in Chronicle, but the
  after-action decision timeline omitted it; the Reports policy-decision count was zero.
- **P2 transient Inspector/command-bar posture mismatch:** STILL PRESENT. In the same run at
  SEQ `428`, Inspector showed `contained`/`Isolated` while the bottom command bar briefly showed
  `normal`.
- **P2 header debrief state lagged report generation:** STILL PRESENT. In
  `run_V3B7K2HC4JYJ39WQHSNNH8P0C5`, seed `1427798730`, sim `00:06:15Z` / SEQ `284`, the
  immediately-ended cockpit showed `DEBRIEF PENDING`; opening After-action refreshed it to
  `REPORT READY`.
- **P2 copilot first attempt fails before recovery:** STILL PRESENT. WATCHTOWER failed at SEQ
  `432` before recovery at SEQ `437`; TRACE failed at SEQ `441`, and BASTION failed at SEQ
  `448` in the same run.

### New defects

- **P1 - Tutorial required Observe objective cannot advance.** Repro in
  `run_E02AHM3GRDCYE9CDMM1PBTD3D1`, seed `1000`, sim `00:21:40Z`, replay cursor/action
  `SEQ 328`. In chapter 4, select Instructor Workstation Alpha from Node Index, reopen the
  tutorial, and click Observe. The toast says `ACTION EXECUTED Observe`, Inspector changes to
  under observation, and the timeline records `action.executed`, but the objective remains gold
  and Next stays disabled. Repeating the action does not unlock the beat; the run ends at SEQ
  `412` with the objective unmet. This makes the required tutorial path impossible to complete.
- **P1 - Operator Alpha cannot start the deterministic tutorial after Admin owns it.** Repro
  after Admin's `run_E02AHM3GRDCYE9CDMM1PBTD3D1` (seed `1000`, terminal sim `00:25:00Z` / SEQ
  `412`) is stopped: sign out, sign in as Operator Alpha, click the tutorial start control.
  The catalogue errors before launch with the message that the run belongs to another operator
  and only its owner or an administrator can restart it. The new attempt has no run id, seed,
  sim time, or SEQ because no run is created. This is a hard identity/training dead end.
- **P2 - Copilot tasks can remain orphaned as Working after run termination.** Repro in
  `run_1QGA6JBQP0XHVTVETRFRSQT2S0`, seed `1327565196`, sim `00:10:08Z`: TRACE retry is still
  working after SEQ `442`; BASTION starts at SEQ `447`, fails at SEQ `448`, and remains a
  Working/spinning card with no proposal or terminal state when the run stops at SEQ `452`
  (replay extends to SEQ `453`). This violates the no-orphaned-running-task requirement and
  gives the operator no honest answer about whether to wait.
- **P2 - Separate Reports omits completed AI investigation artifacts.** Repro in
  `run_1QGA6JBQP0XHVTVETRFRSQT2S0`, seed `1327565196`, sim `00:10:08Z`; WATCHTOWER completes
  at SEQ `437` and Chronicle contains agent session/task/tool events. Reports v1 for sequences
  `1-450` says `Evidence attachments: 0`, `Hypotheses: 0`, `Proposals: 0`, `Policy decisions:
  0`, and `No agent investigation artifacts were recorded`. The separate report is therefore
  not a faithful record of the AI teammate interaction.
- **P3 - Silent Relay horizon is opaque.** The unattended run
  `run_V3B7K2HC4JYJ39WQHSNNH8P0C5`, seed `1427798730`, and the controlled run
  `run_FY3RA94A9DBY3QWC38HMFTMRM3`, seed `872356573`, both terminate at sim `00:06:15Z`
  (SEQ `284` and `297`) with failed outcomes and reports. There is no visible horizon label or
  terminal explanation in the live cockpit, so a student can read the fixed boundary as a
  premature stop. This is not a hang, but it is confusing and much shorter than the 25:00
  tutorial horizon.

### UX observations, ranked

1. The evidence contradiction is the highest-impact trust failure; an AI teammate that cannot
   agree with its own Evidence tab is unsafe to learn from.
2. The tutorial feels disciplined until the first required state-changing Observe beat, then
   becomes impossible to finish. Shared deterministic-run ownership compounds that failure for
   another operator.
3. The consequence modal is excellent operator education: class, blast radius, reversibility,
   downstream dependencies, justification, and Stand down/Confirm are all explicit.
4. The graph -> Signals -> Inspector -> Chronicle flow is coherent. Alert asset links focus the
   graph, cause reveals land visibly, and the board changes persist without Resync.
5. The local-model UI makes latency visible, but provider failures and post-stop Working cards
   do not give enough lifecycle truth. A task cancel/expired state is needed.
6. Replay is the strongest audit surface: real topology at Start/middle/End, state digests,
   incident bookmarks, and 2D/3D parity are all useful.
7. Both themes are readable. At 1200px the page remains usable, but the graph/Inspector/console
   competing for width makes investigation slower and increases scan cost.
8. The unlabelled 6:15 live horizon should be explained as a scenario outcome or horizon in the
   operator-facing UI.

### Verdict

**NOT READY.** The core graph, alert navigation, fog/reveal, consequence gate, durable actions,
pause/resume, replay topology, and terminal report generation work. The product still fails the
mission-critical teaching loop: the tutorial cannot complete, Operator Alpha cannot start the
requested isolated tutorial path, the copilot contradicts Evidence and does not return actionable
IDs, the agent proposal path fails before approval, and the debrief/Reports surfaces omit central
operator and AI decisions. This is not GOOD or GREAT; there are two new P1s in addition to the
known P1s.

### Fix-first

1. Make copilot and Evidence use one run-scoped catalogue; validate every cited ID before
   completion and return concrete actions grounded in those records.
2. Fix tutorial objective advancement for successful Observe and give each operator a safe
   tutorial start/reset path without cross-operator ownership dead ends.
3. Persist executed actions, consequences, justifications, and copilot sessions/tasks into both
   After-action Timeline & decisions and the separate Reports page.
4. Finalize or cancel all agent tasks on failure and run stop; expose provider errors and make
   TRACE/BASTION retries produce a bounded terminal result and a real proposal/approval gate.
5. Unify Inspector, command bar, header posture, and debrief/report readiness projections to
   remove visible state races.
6. Label the Silent Relay horizon/outcome and tighten the below-1280 layout after the blocking
   correctness fixes.

## Luna OpenRouter provider playthrough — 2026-08-07

### Driver

- Native visible computer use through `@oai/sky` drove Chrome at `http://localhost:3000` for
  all four runs. The native driver was available; no Playwright fallback was used.
- The existing OpenRouter connection was selected without opening any key-entry form or
  changing, revealing, replacing, or disconnecting credentials.

### Runs

- `run_BEPFH1WBC7K3GDBBYMF3WXBQP3`, seed `2125640506`: OpenRouter / model
  `deepseek/deepseek-v4-flash-0731`; ROE `Investigate`; Bias guard `ON`; Threat tempo `ON`;
  commander's intent present: `Protect student records; preserve evidence; isolate only
  confirmed compromise.` WATCHTOWER triage completed before terminal; run ended at sim
  `00:06:15Z` / SEQ `296`, report ready, score `47.7/100` (`F`).
- `run_662SCNNJ2CJDGGJJHFCKNXGD73`, seed `842859928`: OpenRouter / model
  `deepseek/deepseek-v4-flash-0731`; ROE `Observe`; Bias guard `OFF`; Threat tempo `OFF`;
  commander's intent absent. Followed the SSO Broker alert and executed Observe at about sim
  `00:02:55Z` / SEQ `128`; the asset was durably under observation by sim `00:03:18Z` / SEQ
  `150`. Run ended at sim `00:06:15Z` / SEQ `298`, report ready.
- `run_0N4ESYQAKZ1E99BRR7BXDVB2P4`, seed `1352770460`: OpenRouter / model
  `deepseek/deepseek-v4-flash-0731`; ROE `Forward-deployed`; Bias guard `ON`; Threat tempo
  `ON`; commander's intent absent. WATCHTOWER was sent at sim `00:02:08Z` / SEQ `88` and
  completed around sim `00:04:40Z` / SEQ `197` with alert IDs. TRACE was sent at sim
  `00:05:30Z` / SEQ `240` and remained Working; BASTION was not reachable because the UI
  required an open incident. I stopped the run at sim `00:08:12Z` / SEQ `361` after report
  generation was ready; the copilot still displayed TRACE as Working.
- `run_H2BZ50K14MGBQY921ZKXKC8WB0`, seed `1528588529`: OpenRouter / model
  `deepseek/deepseek-v4-flash-0731`; ROE `Investigate`; Bias guard `OFF`; Threat tempo `OFF`;
  commander's intent present: `Protect student records; isolate confirmed compromise; preserve
  evidence.` Opened the SSO Broker alert case and executed the gated Class 2 Isolate service
  action at sim `00:05:15Z` / SEQ `238` with an audited justification. Run ended normally at
  sim `00:06:15Z` / SEQ `291`, report ready; after-action score `46.9/100` (`F`).

### Provider integration verification

- The OpenRouter card showed Connected on every loadout, and the type-to-filter picker exposed
  and accepted the exact model ID `deepseek/deepseek-v4-flash-0731` on every run.
- Cloud-model agent execution worked for WATCHTOWER on runs 1 and 3. Run 3's WATCHTOWER
  answer cited three exact-looking alert IDs and prioritized the newest SSO Broker alert; run 1's
  Evidence search independently showed matching run-scoped authentication/alert records. No
  provider error was observed.
- TRACE did not complete on run 3: it stayed Working rather than surfacing an attributed
  provider/task failure. BASTION was explicitly unavailable on runs 3 and 4 with the message
  that an open incident was required; no proposal was produced.
- The live header and after-action/report header showed the loadout chips (ROE, toggles, and
  intent) but did not show an OpenRouter/provider chip or the pinned model string. This is
  recorded as a new defect below.
- The Class 2 gate displayed consequences and blast radius, accepted the real justification,
  executed isolation, and showed `contained` / `Isolated` in Inspector and Chronicle. The
  after-action Timeline & decisions retained the approval and justification at SEQ `238`.

### Known-defect recheck (deltas only)

- **P1 evidence-catalogue contradiction: better in these cloud runs.** WATCHTOWER did not
  claim a zero-item catalogue; run 3 returned exact alert IDs, and run 1's Evidence surface
  independently showed matching run records. This is a playthrough delta, not a global closure
  claim.
- **P1 after-action Timeline & decisions omission: better/fixed on run 4.** The executed
  isolate appears as `Operator approved` at SEQ `238` with its justification; the prior omission
  was not reproduced.
- **P2 Inspector/command-bar posture race: better/no repro after run 4 isolate.** Both surfaces
  showed the target contained/Isolated after the toast.
- **P2 report/debrief readiness lag: better/no repro.** Runs 1, 2, and 4 showed report ready at
  terminal; run 3 became report ready after the explicit stop.
- **P2 first-attempt copilot failure: better for WATCHTOWER, worse for cloud TRACE.** WATCHTOWER
  completed without the prior visible first-attempt failure; TRACE exhibited the new persistent
  Working/terminalization failure below.
- **P2 orphaned Working tasks: worse/changed shape under OpenRouter.** The earlier baseline
  defect is directly implicated by run 3's TRACE task blocking the normal horizon and remaining
  Working after stop; see the new P1 below.
- **P2 separate Reports AI-artifact omission: partial improvement only.** Run 4 Reports showed
  grounded claims and agent-task cancellation metadata, but this pass did not establish complete
  persistence of a successful cloud TRACE/BASTION interaction.
- **P3 Silent Relay horizon: same at `00:06:15Z` for normal runs.** Runs 1, 2, and 4 ended at
  that boundary; run 3 exceeded it only because TRACE was still Working.

### New defects

- **P1 — OpenRouter TRACE can remain Working past the horizon and block terminalization.** Repro:
  `run_id=run_0N4ESYQAKZ1E99BRR7BXDVB2P4`, `seed=1352770460`; send TRACE at sim `00:05:30Z` /
  `SEQ=240`; at sim `00:07:55Z` / `SEQ=341` the header still showed `SIM RUNNING` and
  `REPORT UNDERWAY`, while BASTION said `Still working elsewhere: TRACE`; after stopping at
  sim `00:08:12Z` / `SEQ=361`, report became ready but TRACE still displayed Working. This is
  the cloud-provider shape of the earlier P2 orphaned-Working-task defect recorded above.
- **P2 — Run header/debrief omit the pinned OpenRouter provider and model.** Repro:
  `run_id=run_H2BZ50K14MGBQY921ZKXKC8WB0`, `seed=1528588529`; select OpenRouter and
  `deepseek/deepseek-v4-flash-0731`, then inspect sim `00:06:15Z` / `SEQ=291` and the
  after-action page. The header renders Bias guard, Threat tempo, intent, and ROE chips but no
  `OpenRouter` or `deepseek/deepseek-v4-flash-0731` chip, so the provider pin is not operator-
  auditable after launch.
- **P2 — OpenRouter WATCHTOWER completion is slower than the cloud-flow expectation.** Repro:
  `run_id=run_0N4ESYQAKZ1E99BRR7BXDVB2P4`, `seed=1352770460`; send the exact-ID triage prompt
  at sim `00:02:08Z` / `SEQ=88`; the answer renders around sim `00:04:40Z` / `SEQ=197`, after
  tens of wall-clock seconds rather than a seconds-scale response. It completes and is
  attributable to the selected cloud run, but the faster-cadence expectation is not met.

### UX observations

- The provider card and exact model filter are understandable, but the loadout modal requires
  scrolling between ROE/capabilities and provider/model, making full-loadout verification easy
  to lose.
- The cloud WATCHTOWER answer was materially more useful than the earlier zero-catalogue answer:
  it named the newest alert, included exact alert IDs, and stated triage checks. The UI still
  needs a bounded task deadline and honest terminal state for TRACE.
- The BASTION tab explains why it cannot act (`needs an open incident`), but opening an alert case
  did not make a proposal reachable during these runs; the distinction between an alert case and
  an open incident is not obvious.
- The isolate consequence modal is a strong operator pattern. The entered justification was
  visible in Chronicle and the debrief, and the run remained read-only after termination.

### Verdict

**NOT READY for the cloud-model-provider flow.** Four OpenRouter runs launched successfully with
the exact requested model, live cloud WATCHTOWER execution and evidence-grounded output worked,
the gated isolate action and after-action report worked, and normal runs reached the 00:06:15
terminal boundary. Release confidence is blocked by the missing provider/model audit chip, the
cloud TRACE task that can block terminalization and remain Working after stop, and cloud
WATCHTOWER latency that is still tens of seconds rather than seconds.
