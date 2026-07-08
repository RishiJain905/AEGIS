# Phase 23 Handoff — SCRIBE

## Status

`READY FOR VALIDATION`

## Implemented

Phase 23 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/23-scribe.md`:

- **SCRIBE** — evidence-linked after-action reporting with deterministic assembly + optional model narrative
- **Reports service** — `services/reports` (`aegis_reports`): assembler, timeline, template fallback, grounding, export, `ReportService`
- **Contracts** — `AfterActionReportSourceV1`, `AfterActionReportV1`, `ReportClaimV1`, `ReportCitationV1`, `ReportVersionV1`, `ReportExportArtifactV1`, `GroundingValidationResultV1`, `TriggerScribeRequestV1` in canonical `contracts-python` / `contracts-ts` (spec `packages/report-contracts/**` mapped per repo convention)
- **Persistence** — migration `010_scribe_reports`, `PostgresReportRepository`, immutable version + export artifacts
- **API** — `GET /api/v1/runs/{run_id}/after-action-report`, versions, exports; `POST .../investigation/trigger-scribe`
- **Frontend** — `/reports` page, `ReportsPanel` in inspector, claim categories, timeline, export metadata, fixture data
- **Realtime** — `report.version.created`, `report.generation.completed`, `report.generation.failed` projector entries
- **Tests** — `tests/reports/`, `tests/agents/scribe/`, `tests/integration/agents/test_scribe_flow.py`
- **Harness** — `scripts/run_scribe_harness.py`, `apps/web/scripts/capture-scribe-demo.mjs`
- **ADR** — `0024-scribe-evidence-linked-reporting.md`

**Explicitly not implemented:** approval execution (Phase 24), replay (Phases 25–26), scoring rubric / hidden-cause reveal (Phase 29).

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/reports.py`, `packages/contracts-ts/src/reports.ts` |
| Reports service | `services/reports/src/aegis_reports/**` |
| Migration | `migrations/versions/010_scribe_reports.py` |
| Persistence | `packages/persistence/src/aegis_persistence/repositories/reports.py` |
| SCRIBE | `services/agents/src/aegis_agents/roles/scribe/**` |
| API | `apps/api/src/aegis_api/reports/router.py` |
| Frontend | `apps/web/features/reports/**`, `apps/web/fixtures/report-fixture.ts` |
| Tests | `tests/reports/**`, `tests/agents/scribe/**`, `tests/integration/agents/test_scribe_flow.py` |
| Fixtures | `fixtures/model-responses/scribe/**`, `tests/contract/fixtures/valid/*report*` |
| Scripts | `scripts/run_scribe_harness.py`, `apps/web/scripts/capture-scribe-demo.mjs` |
| Docs | `docs/reports.md`, ADR `0024-scribe-evidence-linked-reporting.md` |

## Contracts introduced or changed

| Contract | Version | Notes |
|----------|---------|-------|
| `ReportCitationV1` / `ReportClaimV1` | schema v1 | Claim category taxonomy |
| `AfterActionReportSourceV1` / `AfterActionReportV1` | schema v1 | Deterministic + structured report |
| `ReportVersionV1` / `ReportExportArtifactV1` | schema v1 | Immutable versioning + exports |
| `GroundingValidationResultV1` | schema v1 | Per-claim validation outcome |
| `TriggerScribeRequestV1` | schema v1 | Idempotent trigger API |
| Events `report.version.created`, `report.generation.completed`, `report.generation.failed` | schema v1 | Realtime delivery |
| `WORKSPACE_VERSION` | `0.0.0-phase23` | Compatibility bump |

## Database migrations

- `010_scribe_reports.py` — `report_versions`, `report_export_artifacts`

## Acceptance criteria mapping

| Criterion | Evidence |
|-----------|----------|
| Deterministic assembly from investigation + events | `aegis_reports.assembler`, `test_scribe_acceptance_criteria.py` |
| Timeline ordered by event sequence | `aegis_reports.timeline`, acceptance + integration tests |
| Grounding validates citations; rejects hallucinations | `tests/reports/test_report_grounding.py` |
| Grounding failure → template-only fallback | `aegis_reports.grounding`, `test_report_grounding.py` |
| Regeneration creates new immutable version | `aegis_reports.service`, integration test |
| MD/JSON/HTML exports with checksum | `test_scribe_acceptance_criteria.py` (`render_markdown`, checksum) |
| SCRIBE read-only tools; no execution | `tests/agents/scribe/test_scribe_role.py` |
| Full chain integration | `tests/integration/agents/test_scribe_flow.py` (PostgreSQL) |
| Section 18 acceptance bundle | `tests/reports/test_scribe_acceptance_criteria.py` |

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run pytest tests/reports tests/agents/scribe -q` | **PASS** (8 tests) |
| `uv run pytest -q` | **PASS** (662 passed, 45 skipped) |
| `uv run mypy apps services packages` | **KNOWN ISSUE** — duplicate module path + fastapi stubs (pre-existing) |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm lint` | **PASS** |
| `pnpm test` | **PASS** (59 web tests) |
| `node apps/web/scripts/capture-scribe-demo.mjs` | **PASS** (fixture-mode screenshots) |
| `uv run python scripts/run_scribe_harness.py` | Requires PostgreSQL |
| `uv run pytest tests/integration/agents/test_scribe_flow.py` | Requires `AEGIS_INTEGRATION_POSTGRES=1` + PostgreSQL |

## Visual evidence

Fixture-mode screenshots captured to `/opt/cursor/artifacts/screenshots/`:

1. `01-silent-relay-running.png` — Operation Silent Relay command centre
2. `02-oracle-hypotheses-evidence.png` — Investigation evidence + ORACLE hypotheses
3. `03-bastion-warden-proposal-state.png` — BASTION/WARDEN proposal state
4. `04-scribe-report-summary.png` — SCRIBE after-action report summary
5. `05-scribe-timeline.png` — Synthesized timeline with event references
6. `06-scribe-claim-provenance.png` — Selected claim with linked citations
7. `07-scribe-claim-categories.png` — Fact vs inference vs unsupported badges
8. `08-scribe-export-metadata.png` — Export metadata, version, checksum
9. `09-scribe-agent-audit.png` — Agent session/task lifecycle link
10. `10-scribe-validation-evidence.png` — Unit test output embedded in panel
11. `11-scribe-realtime-update.png` — Reports panel with realtime labels
12. `12-scribe-responsive.png` — Narrow viewport layout

## Architecture decisions and ADRs

- **Created:** [0024-scribe-evidence-linked-reporting.md](../AEGIS-v1.0-Agent-Specs/adrs/0024-scribe-evidence-linked-reporting.md) (Status: **Proposed**)
- Two-layer design: deterministic `aegis_reports` authority + SCRIBE optional narrative via Phase 19 runtime
- Grounding failure → template-only fallback with `groundingFallback: true`
- Regeneration → new immutable `ReportVersion`, never overwrite

## Known limitations

- PostgreSQL integration harness and `test_scribe_flow.py` not executed in cloud agent environment (no database)
- `human_decision` claim category is structural only until Phase 24
- Full-stack harness requires `docker compose up -d postgres redis` and migrations through `010`
- Screen recording of live report generation not captured (fixture-mode screenshots only)
