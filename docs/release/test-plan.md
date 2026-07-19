# AEGIS v1.0 Release Test Plan

Contract version: `aegis.release-test-plan/v1`  
Evidence contract: [`evidence-manifest.schema.json`](evidence-manifest.schema.json)  
Owner: Phase 34 full-system validation

## Release gate

The canonical command is `scripts/run_release_validation.ps1 -Environment local` on
Windows or `scripts/run_release_validation.sh --environment local` on POSIX. Validation
targets the local production-like Docker Compose stack. `staging` is deliberately refused:
ADR 0033 removed executed staging deployment, and a local run must never be presented as
cloud evidence.

Each run writes `docs/release/evidence/<run-id>.json` and per-command logs below
`docs/release/evidence/<run-id>/logs/`. The JSON is the index; logs are the immutable raw
evidence. A release passes only when every command result is `passed`. Skips inside a gate
must be deterministic, carry a reason, and cannot hide a required local/Docker scenario.

The fixed release scenario identity is `operation-silent-relay@1.0.0`, seed `42`. Existing
golden artifacts remain authoritative; this phase does not update or weaken them.

## Architecture non-negotiables

| Architecture rule | Concrete evidence |
| --- | --- |
| PostgreSQL is authoritative; Redis/browser are projections | `tests/integration/db/test_unit_of_work.py`; `tests/failure-injection/test_stream_recovery.py::test_redis_loss_preserves_authority_and_relay_recovers`; release stages `integration`, `failure-injection` |
| Fixed scenario/version/seed/config is deterministic | `tests/golden-replays/**`; `tests/unit/simulation/test_runtime.py`; release stage `golden-replays`; manifest `scenario` |
| Domain events are append-only, ordered, and atomically paired with outbox rows | `tests/integration/db/test_unit_of_work.py`; `tests/integration/streaming/test_outbox_relay.py`; worker-restart failure test |
| Agent state changes are proposals, never direct simulation mutation | `tests/agents/runtime/test_tool_permissions.py`; `tests/integration/approvals/test_approval_workflow.py`; security stage |
| Class 2/3 actions require deterministic policy and explicit approval | `tests/policy/**`; `tests/security/auth/test_authz_matrix.py`; `tests/integration/approvals/test_approval_workflow.py` |
| Sigma/Graphology 2D is the analysis authority; Three.js is read-only derived presentation | `apps/web/src/features/graph/**` tests and `apps/web/src/features/cinematic/**` tests, executed by the `verify` Vitest stage |
| Cross-language contracts are shared and versioned | `tests/contract/**`; `pnpm check-contracts` within `verify`; manifest schema version |
| Routes/entry points remain thin; business behavior lives in services | `uv run lint-imports`, Python mypy and TypeScript dependency-cruiser stages within `verify` |
| Provider/vendor SDKs remain behind adapters | `tests/agents/provider-conformance/**`; `tests/security/test_provider_egress.py`; provider-mode failure tests |
| Synthetic defensive scope only; no offensive functionality | `tests/security/test_agent_policy_bypasses.py`; dependency/import gates; repository review evidence from `verify` and `security` |
| Performance is measured at every real local boundary | `tests/performance/release/run_performance.py`; `docs/release/performance-budgets.md`; report and browser sub-report referenced by the evidence manifest |
| Browser behavior remains deterministic and capability-aware | `tests/e2e/release/**`; existing fixture profiles; `scripts/run_release_e2e.py`; Chromium required, Firefox/WebKit skip only with a recorded reason |
| Release decisions use explicit records | `docs/release/blocker-policy.md`, `defect-policy.md`, `exception-policy.md`, and `known-issues.md` |

## Phase-group acceptance matrix

| Phase group | Acceptance evidence |
| --- | --- |
| Foundation (00-02) | `verify` formatting, lint, typing, contracts and offline tests; `tests/integration/db/**`; migration failure test |
| Product shell (03-04) | web Vitest, typecheck, lint and build coverage in `verify`; release browser journeys in the optional `e2e` stage |
| Graph platform (05-07) | graph domain/unit/worker tests under `tests/graph-domain`, web graph tests, deterministic fixture checks in `verify`, and target/stress browser budgets in the optional `performance` stage |
| Scenario and simulation (08-10) | `tests/scenario-sdk/**`, `tests/simulation-domain/**`, golden replay stage, simulator restart/checkpoint failure test |
| Realtime platform (11-13) | `tests/integration/streaming/**`, `tests/integration/websocket/**`, Redis/worker/WebSocket failure tests |
| Detection and ML (14-17) | feature, detection, ML and risk unit/integration tests in `verify` and `integration`; deterministic fixtures only, no retraining |
| Agent system (18-23) | agent runtime/integration tests, mock/recorded/unavailable provider tests, provider-outage and session-isolation tests, security prompt/egress gates |
| Human control and replay (24-26) | approval integration/security tests; golden replays; MinIO snapshot fallback and persisted replay-equivalence tests |
| Cinematic and reporting (27-29) | cinematic/scoring/reporting unit and frontend tests in `verify`; replay, cinematic replay, SCRIBE, and scoring journeys in the optional `e2e` stage |
| Production readiness (30-33) | `tests/security/**`, `tests/deployment/**`, local production overlay build/smoke via `verify -Deployment`, auth/observability tests |

## Phase 34 acceptance criteria

| Criterion | Required evidence and pass condition |
| --- | --- |
| Every critical architecture criterion has evidence | Every row in the architecture table resolves to a passing command result and retained log in the manifest |
| Golden causes/branches pass end-to-end | `golden-replays` is `passed`; the follow-on release-journey job adds browser journeys without changing this contract |
| Replay, recovery, authorization, and approval invariants are proven | `integration`, `failure-injection`, and `security` are all `passed` |
| Performance/security gates pass or have approved exceptions | `security` must pass. With `--include-performance`, the schema-versioned performance report must pass every measured budget; capability skips and known exceptions must be explicit and retained |
| Release journeys cover the operational golden path | With `--include-e2e`, Playwright covers scenario open/start, live graph, alert triage, mock agent workflow, approval approve/reject/modify, SCRIBE, snapshot, replay/cinematic replay, scoring, keyboard/reduced-motion, state fixtures, narrow layout, and the installed browser matrix |
| Policy records are actionable | Blocker ladder, defect fields, Phase 32-linked exception record, and current known issues exist under `docs/release/` |

## Failure-injection matrix

| Scenario | Boundary and assertion |
| --- | --- |
| Redis loss/recovery | Stop/start the Compose Redis service; PostgreSQL event/outbox survives; relay resumes; PostgreSQL WebSocket recovery provides ordered catch-up |
| Worker restart mid-relay | Restart the Compose worker with a claimed row; stale claim is recovered; one event is published exactly once on retry |
| WebSocket reconnect/gap | PostgreSQL cursor backfill is contiguous; a gap above threshold returns `WS_SEQUENCE_GAP`, requiring snapshot bootstrap before further deltas |
| Simulator/API restart | Restart both Compose services; persisted checkpoint restores the same sequence; API health returns and run state remains durable |
| Provider outage | Unknown/unavailable provider returns a stable structured error; PostgreSQL incident/run operations continue with no provider configured |
| Agent failure isolation | One task/session reaches explicit failed state; a peer mock-provider session completes; run/incident authority is unchanged |
| Snapshot fallback | Corrupt and missing archives in real MinIO are rejected; replay falls back to PostgreSQL events and marks corrupt metadata incompatible |
| Replay equivalence | Full PostgreSQL replay and MinIO snapshot-plus-tail replay have identical normalized state digests and an empty diff |
| Migration behavior | A temporary real PostgreSQL database upgrades empty-to-head, downgrades one revision, then upgrades prior-head-to-head |

## Commands and failure behavior

The runner records and continues through all stages so one failure does not erase later
diagnostic evidence. Any non-zero stage makes the manifest and final verdict fail.

1. `scripts/verify.ps1` — complete offline gate; must end `VERIFY: PASS`.
2. `docker compose up -d --build --wait postgres redis minio api worker simulator` — build the
   current checkout and start the required real boundaries.
3. `uv run python tests/performance/release/run_performance.py` when `--include-performance` is supplied; its report is written under the run directory.
4. `uv run python scripts/run_release_e2e.py` when `--include-e2e` is supplied; it runs `tests/e2e/release/**` and writes its report under the run directory.
5. `uv run pytest tests/integration -q`.
6. `uv run pytest tests/golden-replays -q`.
7. `AEGIS_RUN_FAILURE_INJECTION=1 uv run pytest tests/failure-injection -q`.
8. `uv run pytest tests/security -q`.
9. `scripts/verify.ps1 -Deployment` — production overlay validation/build, local vertical smoke, and teardown.

The extended command is `scripts/run_release_validation.ps1 -Environment local -IncludePerformance -IncludeE2e`
(or the equivalent POSIX flags). The default command remains headless and does not start
Playwright or performance stages.

The final stdout line is exactly `RELEASE VALIDATION: PASS` or
`RELEASE VALIDATION: FAIL`. Command-not-found, Docker startup failure, an unexpected skip,
test failure, deployment smoke failure, or evidence-write failure is a release failure.
