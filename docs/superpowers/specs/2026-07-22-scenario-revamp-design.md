# AEGIS Scenario Revamp — Design (2026-07-22)

Status: approved direction from product owner (autonomous session; owner granted design latitude). Implementation phased below.

## Problem

1. **Mock leakage.** The shipped web bundle runs in `fixture` data-source mode: `apps/web/lib/api/create-client.ts` defaults to `'fixture'`, `apps/web/Dockerfile` never bakes `NEXT_PUBLIC_AEGIS_DATA_SOURCE` (a build-time var), and local `.env` pins `fixture`. Every account therefore sees the fixture dataset — phantom running runs, a 38-node graph, after-action and report content the user never created. Additionally the dev DB contains junk rows (`scenario:streaming-test`, ownerless `run_01ARZ3NDEKTSV4RRFFQ69G5FAV`), and reports/replay/scoring/investigation routers lack per-run ownership checks (any authenticated user can read any run's artifacts by ID).
2. **Runs aren't alive.** `POST /api/v1/runs` works, but nothing advances the simulation (manual Step only), detection is never invoked during a run, seed is hardcoded to 1000, "Resume latest run" only navigates, and nothing generates after-action/score on run end.
3. **No gameplay.** There is no way to task or converse with the defensive agents (no free-text input in `CreateAgentTaskRequestV1`, no chat UI), attacker progress is fully visible the moment effects fire (no fog of war), and the training scenario doesn't exist as a real scenario at all (it was a fixture entry).

## Product intent

A scenario is a live blue-team engagement. The player, working with AI agents backed by the local model (llama-serve :8086 via the existing `openai-compatible` adapter), must detect a hidden attack, task agents to investigate, approve containment, and stop the attacker before objectives are lost. Every Silent Relay run draws a random seed → different hidden root cause/branches per run. The Synthetic Training Scenario becomes a deterministic, hand-held tutorial. After-action, reports, replay, incidents, and active-run surfaces all update live from real run data.

## Phase 1 — Evict mocks, close the data gaps (compact, well-specified)

- `create-client.ts`: default data source becomes `'api'`; fixture requires explicit `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture` AND is refused in production builds (throw/console.error + fall back to api). Tests/Storybook/e2e keep working — they already set the var explicitly.
- `apps/web/Dockerfile`: `ARG NEXT_PUBLIC_AEGIS_DATA_SOURCE=api` + ENV before `next build`; `docker-compose.yml` and `docker-compose.prod.yml` pass it in `build.args`. Fix `.env` line 30 → `api`.
- DB cleanup: idempotent dev script to delete the junk scenario/run rows and their dependents.
- Ownership: add the `_authorize_run` pattern (owner-or-admin, NULL owner → admin-only, 404 on missing) to reports, replay, scoring, and investigation routers; extend ownership tests to cover them.

## Phase 2 — Living runs (RNG, tick engine, detection, lifecycle cohesion)

- **RNG seed**: `seed` becomes optional in `POST /runs`; when omitted the server draws a cryptographically random seed (1..2^31-1) and persists it. Determinism contract unchanged (same seed ⇒ same run; golden tests keep pinned seeds). Web catalogue stops hardcoding 1000: Silent Relay launches seedless (server RNG); run page shows the drawn seed.
- **Tick engine**: an asyncio background service in the API process (lifespan-managed — it owns the `RunCommandService` runtime cache, keeping a single writer) steps every RUNNING run on a cadence (`AEGIS_SIM_TICK_INTERVAL_SECONDS`, default 2; `AEGIS_SIM_STEPS_PER_TICK`, default 1). Per-run asyncio lock serializes ticker vs manual commands vs approved executions. Pause/stop respected. When the run's scheduled horizon is exhausted (scenario `simulationSteps`, default 300) the ticker STOPs the run with a completion event.
- **Live detection**: after each tick's new events, invoke the existing incidents pipeline (`run_detection_for_events`) over the new sequence window with a restart-safe per-run cursor. Alerts/incidents now appear during play.
- **Lifecycle cohesion**: on STOP (manual or completion), auto-generate the after-action report and run score via the existing services and emit the events. "Resume latest run" POSTs `/resume` for paused runs before navigating.

## Phase 3 — AI copilot (chat + tasking + local model)

- **Contracts** (Pydantic + Zod + regenerated JSON schemas, additive/schema-versioned): `CreateAgentTaskRequestV1` gains optional `instructions` (operator free text). Agent sessions gain run-scoped mode (nullable incident) so the player can task agents before the first incident exists — recorded as an ADR (`docs/AEGIS-v1.0-Agent-Specs/adrs/`) since the architecture doc says incident-scoped.
- **Runtime**: executor threads `instructions` into the prompt as the operator directive, includes the session's prior task/artifact history as conversation context (bounded), same structured-output + grounding + tool-registry path. No new trust surface: tool allowlists, policy classes, and the approval gate are unchanged; execution tools stay invisible to the model.
- **Chat UI**: new `apps/web/features/agent-chat/` panel on the run page — role selector (WATCHTOWER/TRACE/ORACLE/BASTION + SCRIBE), composer, thread rendering tasks as turns: operator instruction → live tool-call chips (via existing `agent.task.*`/`agent.tool.invoked` WS events) → artifact summary; BASTION proposals render inline as approval cards wired to the existing approve/reject mutations. Provider selection unchanged: `AEGIS_PROVIDER_DEFAULT=openai-compatible` points at llama-serve :8086 (`host.docker.internal:8086/v1` from the API container); CI keeps the deterministic mock provider with new fixtures.

## Phase 4 — Fog of war + tension presentation

- Attacker effects gated by `hiddenConditions` must not leak to the operator until *detected*. Server-side: operator-facing graph/status projections carry a `visibility` flag; hidden status changes render as normal until a reveal event (alert/incident touching the asset, hidden-condition trigger, or `revealAfterSimSeconds`). Reveal emits an event → frontend plays a detection moment (halo pulse; reduced-motion safe). Replay/after-action *after run end* shows ground truth (attacker lane) for the debrief. API must filter hidden state server-side (no client-side secrets).
- 2D/3D presentation may be adapted freely for tension (threat board, objective tracker, exfil countdown when detected) within the graph contract.

## Phase 5 — Synthetic Training Scenario as tutorial

- Real manifest at `scenarios/synthetic-training/` (small asset set, one clear attack path, fixed seed, short horizon) registered like Silent Relay.
- Guided walkthrough overlay in the web app: coach-mark steps bound to real run milestones (launch → watch telemetry → first alert → open incident → task an agent → approve containment → run ends → read after-action). Steps advance on real events; fully deterministic.

## Phase 6 — Replay & cohesion polish

- Replay timeline distinguishes defender actions (chat instructions, agent tasks, approvals, executions) from attacker/simulation events; post-run ground-truth overlay.
- Verify gate green (`scripts/verify.ps1`), golden replays intact, visual verification in Chrome on the rebuilt container.

## Non-goals (this iteration)

- Token-by-token LLM streaming (task-lifecycle streaming only).
- New infra (no Kafka/Neo4j/etc.), no scenario-authoring UI, no multiplayer.

## Risks

- Ticker vs API-process restarts: acceptable — runs pause and resume deterministically from checkpoints.
- Local model quality/latency: copilot must degrade gracefully (task timeout → failed task visible in chat; mock provider fallback for CI).
- Fog of war touches graph projections (shared pipeline): implemented behind schema-versioned additive fields; golden replay hashes must be updated only with explanation if event shapes change.
