# AEGIS Operator Guide

This guide covers the local, simulation-only operator workflow for v1.0. Use the
production-like Compose stack for an operator rehearsal; it is the staging stand-in
defined by [ADR 0033](AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md).

## Start the local stack

Follow [Getting Started](getting-started.md) through the production-like startup
section. Confirm the API and web URLs printed by the startup commands before opening a
scenario.

## Run a scenario

1. Run `uv run python scripts/demo_v1.py --headless` for the deterministic Silent Relay
   walkthrough, or open the web UI and select a validated scenario package.
2. Confirm the scenario identity and seed before starting. The v1.0 demo uses
   `operation-silent-relay@1.0.0` with seed `42`.
3. Use the live graph to inspect assets, relationships, telemetry, and status changes.
4. Use the detection/ML view to inspect detections and model evidence. Model output is
   advisory and does not directly mutate simulation state.
5. Use the agent view to inspect proposed actions. The demo defaults to the deterministic
   mock provider.

## Approvals and replay

Approval-required actions remain pending until an operator explicitly approves or
rejects them. Record the decision reason in the approval UI/API response. Do not treat a
model recommendation as an approval.

Replay is read-only reconstruction of recorded events. Use it to inspect event order,
state transitions, and scoring inputs without changing the original run. If replay
diverges, retain the run ID, event range, and API logs for diagnosis.

## Scoring and after-action review

Open scoring after the run has reached a terminal state. Review criterion-level results,
evidence references, penalties, and the final score together. The after-action view is
the authoritative place to record observations, missed signals, approval decisions, and
follow-up actions; it is not a substitute for the event log.

## Cinematic mode

Cinematic mode is a presentation view over the same simulation state. It does not add
new events or bypass approval gates. Return to the operational graph when making or
reviewing decisions.

## Observability

The local stack exposes:

- API health/readiness: `http://127.0.0.1:8000/health` and `/ready`
- API metrics: `http://127.0.0.1:8000/metrics`
- Grafana: `http://127.0.0.1:3001`
- Prometheus: `http://127.0.0.1:9090`
- Tempo: `http://127.0.0.1:3200`

Use the run ID, correlation ID, and timestamp when moving from a UI symptom to API,
worker, or database logs. The observability details and retention assumptions are in
[docs/observability.md](observability.md).

## Backup and restore

Use the documented [backup and restore runbook](runbooks/backup-restore.md).
Backups are local operator artifacts for this phase. Verify the target directory before
restoring and record the migration head and backup timestamp.

## Safety boundary

AEGIS v1.0 is a simulation platform. See [Security Scope](security/scope.md) for the
defensive, non-production boundary and reporting process.
