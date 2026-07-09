# ADR 0024 — SCRIBE Evidence-Linked Reporting

## Status

Proposed

## Context

Phase 23 requires structured after-action reporting that consumes investigation artifacts from Phases 20–22 while preserving architecture invariants: PostgreSQL authority, deterministic assembly, untrusted model narrative, and no agent execution of containment or approvals.

## Decision

1. **Deterministic assembly authority** — `services/reports` (`aegis_reports`) assembles `AfterActionReportSourceV1` and template `AfterActionReportV1` from PostgreSQL. Model output is never authoritative truth.

2. **SCRIBE agent plugin** — SCRIBE uses the Phase 19 `TaskExecutor` with `phase23-scribe-v1` structured output. `post_process` invokes `ReportService.generate_report()` and persists via the same path as template-only generation.

3. **Immutable versions** — Each generation creates a new `ReportVersionV1` row and export artifacts. Prior versions are never overwritten.

4. **Grounding fallback** — Invalid or hallucinated narrative citations trigger safe template-only fallback with `groundingFallback: true` and `ReportGenerationStatusV1.grounding_fallback`.

5. **Claim taxonomy** — `ReportClaimCategoryV1` distinguishes observed facts, persisted events, scores, investigation evidence, ORACLE hypotheses, BASTION proposals, WARDEN policy decisions, agent inference, unsupported, and uncertain claims.

6. **Contract placement** — Report contracts live in canonical `aegis_contracts.reports` / `@aegis/contracts-ts` per Phase 01 ownership (not a separate `packages/report-contracts` package).

7. **Deferred scope** — Approval execution, replay engines, scoring rubric, and final after-action learning UX remain Phases 24–29.

## Consequences

- Phase 29 may consume `AfterActionReportV1` exports without redefining report semantics.
- Phase 24 may populate `human_decision` claim citations from approval records.
- Reports remain read-only artifacts; they cannot mutate simulation or evidence stores.

## References

- `docs/AEGIS-v1.0-Agent-Specs/agent-system/23-scribe.md`
- ADR 0020 — Agent Runtime Foundation
- ADR 0023 — BASTION/WARDEN Policy and Proposals
- `docs/reports.md`
