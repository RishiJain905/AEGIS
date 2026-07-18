# Phase 34 Handoff — Full-System Validation

## Status

`READY FOR VALIDATION`

Per ADR 0033, "staging" targets are the local production-like stack; no cloud environment exists or was used.

## Implemented

- **Release test plan** (`docs/release/test-plan.md`): maps every architecture non-negotiable and phase-group acceptance criterion to concrete evidence (test file, command, artifact), with a schema-versioned **test-evidence manifest** contract (`docs/release/evidence-manifest.schema.json`); manifests are written per run under `docs/release/evidence/`.
- **Release validation harness**: `scripts/run_release_validation.ps1` / `.sh` over shared `scripts/release_validation.py`. Stages: offline verify gate → integration (real PostgreSQL/Redis/MinIO) → golden replays → security suites → failure injection → deployment smoke (prod-like compose up→smoke→down) → optional `--include-performance` / `--include-e2e`. Final line `RELEASE VALIDATION: PASS|FAIL`; `--environment staging` refuses without explicit configuration.
- **Failure-injection suite** (`tests/failure-injection/`, docker-gated, 11 passed / 2 conditional skips): Redis loss/recovery (PostgreSQL stays authoritative, relay resumes, WS resync), worker restart (no lost/duplicate events), WebSocket reconnect (contiguous cursor catch-up; `WS_SEQUENCE_GAP` → snapshot bootstrap), simulator/API restart recovery, model-provider outage (structured degradation; core operates with no provider), agent failure isolation, corrupt/missing snapshot fallback to events, replay equivalence (snapshot+tail ≡ full replay), migration matrix (empty→head, prior-head→head, one-step downgrade) on a real temporary database.
- **Provider-mode validation**: mock, recorded, and completely-unavailable modes pass; live/local modes skip with explicit configuration reasons (never required).
- **Performance suite** (`tests/performance/release/`, budgets in `docs/release/performance-budgets.md`, schema-versioned report into the evidence manifest). All budgets pass; measured p50/p95/p99 (ms): API reads 215/307/312 (budget 300/500/750); API command 21/245/290; outbox→Redis→WS 111/124/126 (250/750/1500); event-range query 2/4.8/37; snapshot load 0.7/0.8/2.1; incident list 0.5/0.7/2.3; 2D target layout 1885 (8000); 2D stress 18009 (20000); 3D mount-to-visible 1077 (8000).
- **Release e2e journeys** (`tests/e2e/release/`, Playwright): 5/5 Chromium journeys pass — auth; scenario start/open + live graph; alert triage + WATCHTOWER/TRACE/ORACLE/BASTION with mock provider; approval approve/reject/modify; snapshot → replay → cinematic replay → SCRIBE/scoring. Plus keyboard-only, reduced-motion, responsive (desktop/narrow), and loading/empty/error/disconnected states. Firefox/WebKit skipped-with-reason (executables not installed).
- **Release policies** (`docs/release/`): blocker severity ladder, structured defect contract, exception policy linked to the Phase 32 exception-record, and `known-issues.md` (web image 23 fixable HIGH transitive findings; 3D first-render latency baseline; Windows local `pnpm build` symlink EPERM).

## Defects found and fixed during validation (with regression coverage)

1. Base-compose simulator service exited code 2 (missing `service` subcommand) — fixed in `docker-compose.yml`.
2. Release runner crashed on Windows Unicode console output — UTF-8-safe console configuration.
3. TRACE recorded-provider fingerprint stale after Phase 32 added scenario-data messages — fixture manifest + recorded key updated (intentional, documented).
4. Full-suite pytest collection rejected nested plugin registration — integration fixtures imported directly.
5. WebSocket gateway consumer did not recreate its Redis consumer group after a Redis reset, and `decode_responses=False` byte fields were stringified as `"b'payload'"`, rejecting valid events — both fixed in the consumer path (found by the streaming-lag measurement).
6. Large-graph accessible-list rendering performance defect — fixed.

## Files added / modified

Added: `docs/release/{test-plan.md,evidence-manifest.schema.json,performance-budgets.md,blocker-policy.md,defect-policy.md,exception-policy.md,known-issues.md}`, `docs/release/evidence/*.json`, `scripts/{run_release_validation.ps1,run_release_validation.sh,release_validation.py,run_release_e2e.py}`, `tests/failure-injection/**`, `tests/performance/release/**`, `tests/e2e/release/**`. Modified: `docker-compose.yml` (simulator command), WebSocket gateway consumer (Redis decode/recovery), accessible-list rendering, evidence schema/test-plan extensions.

## Contracts introduced or changed

Release test plan, test-evidence manifest (schema-versioned JSON), performance budget report, blocker/defect/exception/known-issue policies. No durable domain event/API contracts changed. The TRACE recorded-provider fingerprint update is a versioned fixture change with rationale (Phase 32 prompt-assembly addition).

## Database migrations

None added; migration behavior itself validated (see failure-injection matrix).

## Environment and configuration changes

None beyond optional env-tunable load parameters for performance tests (documented in performance-budgets.md).

## Commands executed and results

- `scripts/run_release_validation.ps1 --environment local` (full, incl. performance + e2e stages, executed by implementers and re-run independently by the orchestrator): `VERIFY: PASS`, `DEPLOY SMOKE: PASS`, `RELEASE VALIDATION: PASS`. Evidence manifests: `docs/release/evidence/release-20260718T161638Z-bdc9fadb.json`, `release-20260718T180513Z-bdc9fadb.json` (+ orchestrator rerun manifest).
- Suite tallies: offline 962 passed/15 skipped; integration 47 passed/6 skipped; goldens 10 passed; security 55 passed; failure injection 11 passed/2 skipped; e2e 5/5 Chromium journeys.
- Orchestrator live-browser validation (Chrome): scenarios, run view, 2D/3D graphs, fresh-mount 3D framing, styled 404 error state — pass.

## Architecture decisions and ADRs

No new ADR required. ADR 0033 (deployment readiness) governs the staging-less validation scope. No architecture rule changed; all validation used existing canonical interfaces.

## Known limitations

- Firefox/WebKit e2e coverage skipped locally (executables not installed); chromium covered. CI can extend the matrix.
- Performance numbers measured on the local dev machine; budgets set with generous headroom and recorded as baselines, not SLAs.
- Live/local provider modes validated only for graceful skip/degradation (no credentials/endpoints configured — by design).

## Deferred work

- Browser-matrix expansion and load testing at cloud scale (post-activation task per ADR 0033).

## Risks for dependent phases

- Phase 35 must reference the evidence manifests and policies as release-verification artifacts and keep `run_release_validation` the canonical release check.
- The recorded TRACE fingerprint is now Phase-32-aware; future prompt-assembly changes must re-record with rationale.

## Acceptance criteria evidence

- _Every critical architecture criterion has evidence_ — test-plan.md maps each to test/command/artifact; evidence manifests validate against the schema.
- _Golden causes/branches pass end-to-end_ — golden replays 10/10; e2e journeys across the Silent Relay flow 5/5.
- _Replay, recovery, authorization, and approval invariants proven_ — failure-injection suite + security suites (55 passed) + approval e2e paths.
- _Performance/security gates pass or have explicit approved exceptions_ — all performance budgets pass; security gates pass with the web-image transitive findings under the documented exception policy.

## Prohibited-shortcut confirmation

No tests weakened or deleted; goldens untouched except the documented recorded-provider fixture re-record; real service boundaries used for integration/failure tests; all commands executed on this tree; defects fixed with regression coverage rather than skipped.
