# ADR 0025 — Approval Workflow

## Status

Proposed

## Context

Phase 22 delivered BASTION proposals and deterministic WARDEN policy evaluation. Class 2/3 proposals remain `pending` with `approval_required`. Architecture requires important state changes to pass deterministic policy, explicit human approval, final revalidation, and an internal idempotent simulator command. Production OIDC is deferred to Phase 30, but actor hooks must exist now.

## Decision

1. **Backend-enforced human approval** — Approve / reject / modify / cancel are FastAPI routes that write `ApprovalV1` (and related records) in PostgreSQL. Frontend controls are projections only.

2. **Final WARDEN revalidation** — Immediately before execution, `PolicyEngine.evaluate` runs against the proposal's current revision. Stale revision or `block` fails closed. Human approval satisfies `approval_required`; it does not bypass `block`.

3. **Optimistic concurrency** — Requests carry `expectedRevisionId` and `expectedRevision`. Mismatch returns `STALE_PROPOSAL`.

4. **Authorized simulation command adapter** — Allowlisted scenario commands map to `SimulationCommandType.EXECUTE` with `effect.set_asset_status` payloads. Operator actor + `synthetic-operator-token` are required until Phase 30.

5. **Idempotent execution** — Approval scope idempotency keys plus unique `(run_id, idempotency_key)` on `executed_actions` prevent duplicate effects under retries.

6. **InvestigationDetail v4** — Additive `approvals[]` and `executedActions[]` for command-centre reconstruction after reload.

7. **Actor identity hook** — Optional `X-Actor-Id` / request `actorId` defaulting to `asset:operator-console`. Phase 30 replaces the synthetic token and identity source without changing the approval state machine.

## Consequences

- Class 2/3 proposals cannot execute without a persisted human approval and final policy check.
- Modified proposals append revisions and force WARDEN re-evaluation before any later approve.
- Replay phases can reconstruct approval/execution from append-only events.
- SCRIBE may cite human decisions from `ApprovalV1` records.

## References

- `docs/AEGIS-v1.0-Agent-Specs/human-control-and-replay/24-approval-workflow.md`
- ADR 0023 — BASTION/WARDEN Policy and Proposals
- ADR 0010 — Deterministic Simulation Core
- ADR 0020 — Agent Runtime Foundation
- `docs/approval-workflow.md`
