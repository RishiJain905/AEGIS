# ADR 0023 — BASTION/WARDEN Policy and Proposals

## Status

Proposed

## Context

Phase 22 introduces BASTION as the response-planning agent and WARDEN as the deterministic policy evaluator. BASTION must consume ORACLE hypotheses and investigation evidence to propose allowlisted scenario commands. WARDEN must evaluate proposals without model authority — policy outcomes are computed by pure functions in `packages/policy`.

## Decision

1. **Proposal revision model** — Rich proposal content lives in append-only `ProposalRevisionV1` records. `ActionProposalV1` v2 is the identity anchor with `currentRevisionId` and `scenarioCommand`. Re-triggers append revisions; history is never deleted.

2. **Deterministic policy boundary** — `PolicyEngine.evaluate(PolicyInputV1)` in `packages/policy` is the sole authority for `allow` / `block` / `approval_required`. WARDEN `post_process` computes the decision before persisting; model output may only populate non-authoritative `explanationProse`.

3. **BASTION/WARDEN tool separation** — BASTION uses `create_response_proposal`; WARDEN is read-only. Execution-class tools, hypothesis mutation, and direct `create_action_proposal` are excluded from both role maps.

4. **Class 2/3 approval gate** — Operational and critical proposals always receive `approval_required`; proposal status stays `pending`. Incident may transition to `approval_pending`. Phase 24 owns approve/reject/execute.

5. **Persistence tables** — `proposal_revisions` and `policy_decisions` stored in PostgreSQL (`009_bastion_warden_proposals` migration) with schema-versioned JSON payloads.

6. **Investigation aggregation** — `InvestigationDetailV1` v3 includes proposal and policy artifacts for command-centre UI and downstream phases.

7. **Deferred approval execution** — No approve/reject routes, approval UI actions, or simulator command execution in Phase 22. UI displays read-only approval-required state.

## Consequences

- Phase 24 must revalidate policy against current revision before execution (stale revision block is already implemented).
- SCRIBE (Phase 23) can cite `PolicyDecisionV1` and proposal revisions in reports.
- BASTION cannot bypass WARDEN; proposals are always evaluated after creation.
- `packages/policy` remains dependency-isolated (contracts only).

## References

- `docs/AEGIS-v1.0-Agent-Specs/agent-system/22-bastion-and-warden.md`
- ADR 0022 — ORACLE Hypothesis Generation
- ADR 0020 — Agent Runtime Foundation
- `docs/policy-and-proposals.md`
