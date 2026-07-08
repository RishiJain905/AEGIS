# SCRIBE After-Action Reporting (Phase 23)

Phase 23 introduces **SCRIBE**, the evidence-linked after-action reporting agent and deterministic report service.

## Responsibilities

- Assemble `AfterActionReportSourceV1` from PostgreSQL investigation artifacts, domain events, alerts, and risk scores
- Synthesize timelines from authoritative persisted events (monotonic sequence ordering)
- Generate deterministic template reports without requiring a model
- Optionally merge grounded SCRIBE narrative from the Phase 19 agent runtime
- Validate all claim citations; reject hallucinated references safely
- Fall back to template-only output when grounding fails
- Persist immutable `ReportVersionV1` records and Markdown/JSON/HTML exports
- Emit `report.version.created` and `report.generation.completed` domain events

## Explicit non-responsibilities

SCRIBE does **not**:

- Approve proposals or execute containment
- Mutate simulation state or authoritative evidence
- Implement Phase 24 approval workflow, Phase 25–26 replay, or Phase 29 scoring UX

## Contracts

Canonical contracts live in:

- `packages/contracts-python/src/aegis_contracts/reports.py`
- `packages/contracts-ts/src/reports.ts`

Key types: `AfterActionReportSourceV1`, `AfterActionReportV1`, `ReportClaimV1`, `ReportCitationV1`, `ReportVersionV1`, `ReportExportArtifactV1`, `GroundingValidationResultV1`, `TriggerScribeRequestV1`.

## Claim categories

Reports distinguish:

- `observed_fact`, `persisted_event`, `detection_score`, `graph_risk`
- `investigation_evidence`, `oracle_hypothesis`, `bastion_proposal`, `warden_policy_decision`
- `human_decision` (reserved for Phase 24)
- `agent_inference`, `unsupported`, `uncertain`

## Grounding rules

- Factual categories require resolvable citation IDs present in the assembled source
- Unknown or malformed references downgrade to `unsupported` or `uncertain`
- Batch grounding failure triggers template-only fallback (`groundingFallback: true`)

## API

- `GET /api/v1/runs/{run_id}/after-action-report`
- `GET /api/v1/runs/{run_id}/after-action-report/versions`
- `GET /api/v1/runs/{run_id}/after-action-report/exports/{format}`
- `POST /api/v1/runs/{run_id}/investigation/trigger-scribe`

## Operational commands

```bash
uv run pytest tests/reports tests/agents/scribe -q
PYTHONPATH=. uv run python scripts/run_scribe_harness.py
node apps/web/scripts/capture-scribe-demo.mjs
```
