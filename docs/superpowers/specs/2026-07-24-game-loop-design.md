# AEGIS Game Loop — Design (2026-07-24)

Status: design for sign-off. This is the core the app is missing. Owner decisions locked (2026-07-24): **(1) core loop = race a hidden, advancing attacker; (2) actions = real staged cyber actions with consequences; (3) split = true 2v1 — human acts directly AND tasks an AI that investigates autonomously and proposes actions for approval.**

## The problem this fixes

Today AEGIS has surfaces (copilot, operator console, blast radius, proposals, fog of war, threat tempo, dossier, scoring) but **no game**: nothing is trying to beat you, there's no clock, no felt objective, and "investigate / search evidence" leads nowhere because there's no attacker to find and stop. The simulation emits telemetry and flips some hidden statuses on a fixed schedule, but the operator can't *change the outcome* — actions don't affect an attacker, and there's no win/lose you drive. This spec adds the missing spine: **an active attacker that advances toward a goal on a clock, hidden until detected, whose progress your (and the AI's) investigate + respond actions actually disrupt — with a real win/lose.**

## The loop (what a session feels like)

1. **Something's off.** Telemetry + the first alerts surface. The attacker is already inside, at an early kill-chain stage, hidden by fog of war. A threat-tempo/pressure indicator rises as it advances undetected.
2. **Hunt.** You and the AI **investigate** — search logs/events, trace connections, inspect assets (auth history, running processes, network) — to *reveal* where the attacker is and what stage it's at. Detection also auto-reveals (alerts on an asset disclose it). TRACE/WATCHTOWER run these autonomously when tasked.
3. **Understand.** As stages reveal, the attacker's **path** lights up on the graph (this is what the 2D/3D revamps visualize): entry asset → lateral moves → escalated identity → the data it's collecting. Distractors (benign noise) muddy it — attributing the *real* path matters.
4. **Sever.** You take **real staged actions** to cut the kill chain before it reaches exfil: isolate the compromised host (stops lateral movement from it), kill the malicious process (stops a stage), revoke/reset the abused credentials (cuts identity-based access), block the C2/exfil IP (cuts exfiltration), quarantine, patch/rollback. Each has a **real effect on the attacker's progress** and **collateral** (service impact, evidence loss). The AI (BASTION) proposes these; you approve/execute, or you act directly.
5. **Win or lose.** WIN = the kill chain is severed before exfil completes, proportionately. LOSE = the attacker reaches **exfiltration** (data stolen) — or you **over-contain** and cripple the org (isolating critical services needlessly is its own failure). The after-action + dossier + ghost branch already exist to debrief the outcome.

## Core new component: the attacker kill-chain engine

This is the heart of the build. It extends the existing scenario/simulation engine (deterministic, seeded, `simulation-domain`) — it does NOT replace it.

**Kill-chain model.** An attacker campaign is an ordered set of **stages**, each anchored to an asset and gated by conditions:

`initial_access → lateral_movement (1..n hops) → privilege_escalation → collection → exfiltration`

- Each stage has: an anchor asset, a **dwell requirement** (sim-time it needs to advance to the next stage), **prerequisites** (the prior stage completed on a reachable asset), and an **advance effect** (compromises the next asset, emits the telemetry/signals that detection can catch).
- The attacker **advances on the sim clock**: while undisrupted, each stage accrues progress and, on completing its dwell, advances to the next (choosing the next asset along real relationship edges — lateral movement follows `COMMUNICATED_WITH`/`AUTHENTICATED_TO` edges; escalation follows identity edges; collection targets the crown-jewel data assets; exfil targets an egress asset). This is **seed-deterministic** (same seed ⇒ same attacker path & timing absent player action) so golden replays and RNG-per-run both hold.
- **Fog of war** (already built): a stage's compromise of an asset is undisclosed until detected/revealed. The operator sees the org as calm until their investigation or a detection reveals a compromised asset.

**Disruption — how actions change the outcome.** Each response action maps to a **disruption effect** on the kill chain:

| Action | Effect on the kill chain |
|---|---|
| Isolate host | Severs the asset's edges → lateral movement *out of / through* it stops; if it's the attacker's current foothold, the chain stalls (must re-establish from another compromised asset, if any). |
| Kill process | Halts the in-progress stage on that asset (resets its dwell progress); attacker must restart it. |
| Revoke / reset credentials | Cuts credential-based stages (privilege escalation, lateral moves that used that identity); if it's the identity the attacker holds, escalation collapses. |
| Block IP / egress | Cuts C2 and **exfiltration** — even a completed collection can't leave. Strong late-game save. |
| Quarantine / patch / rollback | Removes the foothold on an asset (eradication) / closes the exploited path. |

The attacker is **adaptive within determinism**: if you sever its current path, it falls back to another *already-compromised* asset to continue (deterministic fallback given seed + world state) — it does NOT magically teleport. Cutting *all* its footholds before exfil = contained = win. This gives real "cut it off in time" tension without a non-deterministic LLM attacker (that stays deferred to a future "adversarial mode").

**Win/lose resolution.** The run resolves to an outcome when: exfiltration completes (LOSE — with what was stolen), OR all attacker footholds are eradicated before exfil (WIN), OR the horizon elapses (scored on how far the attacker got + your response). Over-containment (crippling critical services) applies a heavy penalty and can force a LOSE even if the attacker was stopped. Outcome + a clear win/lose is surfaced in the run and the after-action.

## Investigate toolkit (reveal) — mostly wiring what exists

- **Event/log search** (operator console — exists) and **agent search tools** (exist): make them *reveal kill-chain state* — searching the right asset/time/type surfaces the attacker's signals and discloses that stage.
- **Trace connections** (graph "Trace path" + TRACE agent — exist): reveal the attacker's lateral path along edges.
- **Inspect asset** (new, small): a per-asset "look closer" (auth history / processes / connections) that discloses whether that asset is compromised and at what stage — the core hunting action.
- Detection/ML (exists) continues to auto-reveal via alerts.

The point: investigation **removes fog** on the kill chain. That's the "achieve what?" answer — you search to *find the attacker's position* so you can act on it.

## Respond toolkit (sever) — extends the existing action pipeline

The policy → approval → execution pipeline and the operator-actions + BASTION-proposal paths already exist. This adds: (a) the **disruption effects** above (the missing link — actions currently mutate asset status but don't affect an attacker because there wasn't one), (b) a couple of new action verbs (kill process, block IP) in the command catalog + policy classes, (c) making the actions' effect on the kill chain and the collateral legible in the UI (blast-radius preview already previews collateral — extend it to also preview *"this cuts the attacker's lateral path from X"*).

## The 2v1 (mostly exists — now it has a point)

- **Human acts directly**: operator-actions (exists) now actually disrupt the attacker.
- **AI investigates autonomously**: the autonomy loop (exists) hunts — WATCHTOWER triages, TRACE traces — revealing kill-chain state and posting to the ops feed.
- **AI proposes actions**: BASTION (exists) proposes disruptions targeting the revealed attacker; you approve. Rules-of-engagement (exists) sets how forward the AI acts.
- Both act on the same kill chain; the after-action/dossier already separate the two lanes.

## Objective & pressure UI (new, small but essential)

The game needs to be *felt*: a persistent **objective/status bar** on the run page — attacker's known stage (or "unknown — hunt"), a **threat/exfil pressure** meter (threat tempo exists; when exfil is detected as imminent, an **exfil countdown**), what's contained vs still active, and a clear WIN/LOSE resolution moment. This is what turns the surfaces into a game.

## What's reused vs new

- **Reuse (already built):** simulation engine, scenario contract, fog of war, operator console + search, operator-actions + policy + approval + execution, BASTION proposals, autonomy loop, RoE, threat tempo, blast-radius, scoring, replay, adversary dossier, ghost branch, commander's intent.
- **New (this build):** the attacker kill-chain engine (stages, advancement-on-clock, deterministic path along edges, fallback); action→disruption effects wired into it; kill-chain state in the operator-facing graph projection (fog-respecting); win/lose resolution + outcome; the objective/exfil-pressure UI; "inspect asset" + "kill process"/"block IP" verbs; blast-radius extended to preview attacker-path impact.

## Scenario authoring

`operation-silent-relay` already has hidden causes + branches + assets + zones. Convert its hidden-condition/branch machinery into an explicit kill-chain definition (entry, the lateral/escalation/collection/exfil path per root-cause branch, dwell timings, crown-jewel + egress assets). The 4 seed-selected root causes become 4 attacker campaigns. `synthetic-training` gets one simple, legible kill chain for the tutorial.

## Determinism & non-negotiables (unchanged contracts)

- Attacker progression is **seed-deterministic**; same seed + same player actions ⇒ identical outcome. Golden replays hold (the attacker is just more scheduled/gated sim behavior; no wall-clock, no RNG outside the seeded stream). Player/AI actions are already deterministic commands.
- Fog of war stays server-enforced. No LLM attacker (deferred). No new infra.

## Phasing (build order, each its own gate)

1. **Kill-chain engine** in simulation-domain: stages, clock advancement, deterministic path along edges, fallback; emits the same event types + fog-respecting disclosure. Golden replays updated with explanation. (Backend, heaviest.)
2. **Action → disruption** wiring: response actions actually affect the kill chain; win/lose resolution + outcome on the run.
3. **Kill-chain state in the graph projection** (fog-respecting) so the 2D/3D can render the attacker path as it's revealed. (Coordinates with the visual revamps.)
4. **Objective/exfil-pressure UI** + win/lose moment; extend blast-radius to attacker-path preview; "inspect asset" + new verbs.
5. **Scenario authoring**: silent-relay's 4 campaigns + training's tutorial chain.
6. Cohesion pass: dossier/ghost/replay reflect the kill chain and outcome; full Chrome playthrough of a real win and a real loss.

## Open design choices for owner sign-off

1. **Kill-chain granularity** — the 5-stage model above, or richer (MITRE-ATT&CK-style with more techniques)? Recommend the 5-stage model first; deepen later.
2. **Attacker adaptiveness** — deterministic fallback-to-another-foothold (recommended, keeps replays valid) vs a smarter scripted response to your actions. Both stay non-LLM.
3. **Loss on over-containment** — how punishing? Recommend: over-containment heavily penalizes score and can turn a "contained" into a costly win or a loss if critical services die, so proportionality matters (matches the existing scoring intent).
4. **Where the objective/pressure bar lives** — top status strip (recommended) vs its own panel.
