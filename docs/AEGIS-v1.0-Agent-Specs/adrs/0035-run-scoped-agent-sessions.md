# ADR 0035: Run-scoped agent sessions (operator tasking before the first incident)

## Status

Accepted (v1.0 — Phase 3 AI copilot, scenario revamp design 2026-07-22)

## Context

Section 14 of `docs/architecture.md` describes the agent runtime as an
**incident-scoped state machine**: an `AgentSessionV1` and every `AgentTaskV1`
carried a required `incidentId`, and the runtime derived a task's `run_id` by
loading the incident (`incident.run_id`). Every route to spawn a session was
`POST /incidents/{incident_id}/agent-sessions`.

Phase 3 turns a run into a live blue-team engagement the player drives by
conversing with the defensive agents. The player must be able to task an agent —
"WATCHTOWER, sweep the current telemetry", "TRACE, look at that identity
provider" — **before any incident exists**, since detecting the hidden attack is
the point of the game and the first incident may not have been raised yet.
Anchoring a session to an incident makes that impossible.

## Decision

1. **A session/task anchors to a run; the incident is optional.**
   `AgentSessionV1` and `AgentTaskV1` gain a required `runId` and relax
   `incidentId` to nullable (`incidentId: string | null`). Every session belongs
   to exactly one run (runs are the top-level container per ADR 0034); a
   run-scoped session carries `incidentId = null`, an incident-scoped session
   carries both. This is an additive change within `schemaVersion` 1 — a required
   field is added and a required field is widened to nullable, both consistent
   across `contracts-python` and `contracts-ts`. Migration `016` backfills
   `run_id` (and the JSONB `runId`) from the owning incident for existing rows and
   makes the `incident_id` columns nullable.

2. **New run-scoped routes, incident routes unchanged.**
   `POST /api/v1/runs/{run_id}/agent-sessions` creates a run-scoped session and
   `GET /api/v1/runs/{run_id}/agent-sessions` lists a run's sessions (for chat
   restore). The existing `POST /incidents/{incident_id}/agent-sessions` keeps
   working unchanged. Both new routes are ownership-gated with the shared
   `require_run_access` (owner-or-admin; 404 unknown run, 403 non-owner), matching
   the reports/replay/scoring/investigation routers hardened in Phase 1. The
   `POST /agent-sessions/{id}/tasks` route is now also ownership-gated on the
   session's run (closing a pre-existing gap where any trigger-capable user could
   task any session).

3. **Operator directive (`instructions`).**
   `CreateAgentTaskRequestV1` and `CreateAgentSessionRequestV1` gain an optional
   bounded `instructions` string (≤ 4000 chars). It is threaded into the prompt as
   a delimited, escaped **operator directive** — untrusted human text that may
   steer *what* the agent investigates but never overrides the system prompt, the
   output schema, or any guardrail (same containment pattern as
   `build_scenario_data_message`). The directive is retained on `AgentTaskV1` so
   the chat thread can be reconstructed from task history.

4. **Run-scoped execution keeps every guardrail.**
   The executor derives `run_id` from the session, loads an incident only when
   `incidentId` is set, and for run-scoped tasks: injects a run-scoped scenario
   note instead of an incident title; skips incident-keyed role post-processing
   (which writes triage/hypothesis/proposal rows) while still producing the
   `STEP_RESULT` artifact the chat renders; and fails **soft** on a tool that
   needs an incident (e.g. BASTION's proposal tool with no incident open) — the
   invocation is recorded and streamed as a failed/rejected chip and the grounded
   artifact still lands. Structured-output validation, evidence grounding, the
   per-role tool allowlist, budgets, and bounded retries are unchanged. The
   run-keyed read tools (alerts, events, risk scores, evidence) already operate
   off `run_id`, so WATCHTOWER/TRACE/ORACLE produce useful run-scoped results;
   BASTION reports that it needs an incident before it can propose containment.

## Consequences

- The architecture doc's "incident-scoped state machine" description is now a
  special case of a run-scoped one; §14 should be read with this ADR.
- No new trust surface: execution-class tools remain invisible to the model, all
  state changes still flow through the proposal → policy → human-approval gate,
  and run ownership gates every new route.
- Determinism is unaffected — no simulation event shapes changed; the added
  fields live on agent-runtime contracts, not on normalized simulation events.

## Alternatives considered

- **Synthetic "run" incident.** Auto-open a placeholder incident per run so the
  existing incident-scoped path is reused. Rejected: it pollutes the incident
  table and the operator-facing incident list with a non-incident, and muddies
  scoring/after-action which count real incidents.
- **Keep `incidentId` required, add a separate `runId`.** Rejected: it leaves a
  meaningless required incident id on run-scoped rows and forces sentinel values;
  nullable `incidentId` models the real invariant (an incident may not exist yet).
