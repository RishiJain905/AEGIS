# ADR 0022 — ORACLE Hypothesis Generation

## Status

Proposed

## Context

Phase 21 introduces ORACLE as the hypothesis-generation agent on the Phase 19 generic agent runtime. ORACLE must consume WATCHTOWER/TRACE investigation artifacts, produce multiple competing evidence-grounded hypotheses with explicit contradictions and confidence semantics, and persist append-only revisions without mutating the simulation or bypassing tool authorization.

## Decision

1. **Role plugin pattern on Phase 19 runtime** — ORACLE extends `TaskExecutor` via `OracleRoleHandler` (`output_schema`, `system_prompt`, `post_process`). All model calls use the Phase 18 `ModelProvider` abstraction with prompt version `phase21-oracle-v1`.

2. **Revision-append persistence** — Rich hypothesis content lives in `HypothesisRevisionV1` records. `HypothesisV1` v2 is the identity anchor with `currentRevisionId`. Re-triggers append revisions and supersede prior active revisions; history is never deleted.

3. **Grounding invariant** — Claims are validated against visible `InvestigationDetailV1` evidence and attachments. Unsupported facts are rejected, downgraded to assumptions, or marked `unsupported_claim`. Contradiction links reference visible contradicting evidence.

4. **Hypothesis artifact tables** — `hypothesis_revisions`, `hypothesis_comparisons`, and `verification_requests` are stored in PostgreSQL (`008_oracle_hypotheses` migration) with schema-versioned JSON payloads.

5. **Investigation domain events** — `investigation.hypothesis.created`, `investigation.hypothesis.revised`, `investigation.hypothesis.comparison.created`, and `investigation.verification.requested` are emitted append-only with monotonic run sequence numbers.

6. **Tool boundaries** — ORACLE uses read and analysis-write hypothesis tools only. `create_action_proposal`, `attach_evidence`, and execution-class tools are excluded. Bounded TRACE verification requests are allowed via `request_trace_verification`.

7. **Explicit deferral of later phases** — BASTION/WARDEN response planning, WARDEN policy, approval workflows, SCRIBE reporting, and containment execution remain out of scope.

## Consequences

- Phase 22 BASTION must consume `HypothesisV1` and current revisions via `InvestigationDetailV1` when proposing responses.
- ORACLE produces analysis artifacts only; no simulator commands or action proposals.
- Confidence assessments include range, coverage, and contradiction penalty for downstream policy and reporting.

## References

- `docs/AEGIS-v1.0-Agent-Specs/agent-system/21-oracle.md`
- ADR 0021 — WATCHTOWER and TRACE Investigation Agents
- ADR 0020 — Agent Runtime Foundation
