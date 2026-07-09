# Approval Workflow (Phase 24)

Phase 24 implements operator approve / reject / modify for BASTION proposals, final WARDEN revalidation immediately before execution, idempotent simulator command execution, and full audit history.

## Authority

Human approval is **backend-enforced**. The command-centre UI may display controls, but frontend state is never treated as authorization. Agents, model output, and client code cannot authorize or execute simulation mutations.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: BASTION creates proposal
    pending --> pending: WARDEN approval_required
    pending --> approved: WARDEN allow class 0/1
    pending --> rejected: WARDEN block
    pending --> pending: operator modify + WARDEN re-eval
    pending --> executed: operator approve + final policy + EXECUTE
    pending --> rejected: operator reject
    pending --> cancelled: operator cancel
```

## API

```text
POST /api/v1/action-proposals/{proposal_id}/approve
POST /api/v1/action-proposals/{proposal_id}/reject
POST /api/v1/action-proposals/{proposal_id}/modify
POST /api/v1/action-proposals/{proposal_id}/cancel
```

Request bodies require:

- `expectedRevisionId` / `expectedRevision` (optimistic concurrency)
- `idempotencyKey`
- optional `actorId` (defaults to `asset:operator-console`)

Headers:

- `X-Actor-Id` — operator identity hook (Phase 30 replaces with OIDC)
- `Authorization: Bearer synthetic-operator-token` — synthetic operator token until Phase 30

## Final policy check

On approve, the service:

1. Validates proposal is `pending` and revision matches
2. Re-runs `PolicyEngine.evaluate` against the current revision
3. Persists a new `PolicyDecisionV1` and emits `action.proposal.policy_evaluated`
4. Fails closed on `block` / stale revision
5. Accepts `allow` or `approval_required` only after an explicit human `ApprovalV1`

## Command mapping

Allowlisted `ScenarioCommandTemplateV1` values map to internal `SimulationCommandType.EXECUTE` via `effect.set_asset_status`:

| Command | Asset status |
|---------|--------------|
| `observe` | `observed` |
| `increase_monitoring` | `heightened_monitoring` |
| `isolate` | `isolated` |
| `restrict_access` | `access_restricted` |
| `revoke_credentials` | `credentials_revoked` |
| `restart_service` | `restarting` |
| `rollback_deployment` | `rolling_back` |

Execution uses operator actor + authorization token + idempotency key. Duplicate approve returns the prior `ExecutedActionV1` without double effect.

## Persistence and events

| Record | Table / event |
|--------|----------------|
| `ApprovalV1` | `approvals` |
| `ExecutedActionV1` | `executed_actions` (unique `(run_id, idempotency_key)`) |
| Approved | `action.proposal.approved` |
| Rejected | `action.proposal.rejected` |
| Modified | `action.proposal.modified` |
| Cancelled | `action.proposal.cancelled` |
| Executed | `action.executed` |

`InvestigationDetailV1` v4 aggregates `approvals[]` and `executedActions[]`.

## Failure modes

| Code | Meaning |
|------|---------|
| `STALE_PROPOSAL` | Revision / concurrency mismatch |
| `UNAUTHORIZED` | Missing or invalid operator token |
| `POLICY_BLOCKED` | Final WARDEN check blocked execution |
| `ALREADY_DECIDED` | Proposal not pending |
| `NOT_FOUND` | Proposal / revision / incident missing |
| `EXECUTION_FAILED` | Simulator command failed |

## Constraints for Phases 25–29

- Approval and execution events remain append-only with monotonic per-run sequences for replay.
- Do not treat frontend approval state as authority.
- Actor hooks must remain swappable for Phase 30 OIDC without changing the approval state machine.
- SCRIBE may cite `ApprovalV1` as `human_decision` claims; do not invent decisions during report assembly.
- Replay (25–26), scoring (29), and production auth (30) are out of scope here.

## References

- ADR 0025 — Approval Workflow
- ADR 0023 — BASTION/WARDEN Policy and Proposals
- ADR 0010 — Deterministic Simulation Core
- `docs/policy-and-proposals.md`
