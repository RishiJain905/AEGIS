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
