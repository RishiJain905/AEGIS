# Phase 31 Handoff — Observability

## Status

`READY FOR VALIDATION`

## Implemented behavior (Sections 7 and 18)

| Spec item | Implementation |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Shared OpenTelemetry setup + context propagation | `packages/observability` (`aegis_observability`): `setup.py`, `context.py`, `middleware.py`; API lifespan `init_observability` / `shutdown_observability` |
| Standardized structured fields | `TelemetryContextV1` / `TelemetryContextState`: trace, span, correlation, request, run, incident, agent session, sequence, service, operation, actor, outcome, duration |
| Instrument critical flows | Hooks in API middleware; model-provider; simulation step; approvals; replay; scoring; agents; outbox worker; WebSocket gateway metrics bridge |
| Distinct liveness / readiness / diagnostics | Public `GET /health`, `GET /live`; public `GET /ready` (bounded Postgres/Redis/object-storage probes); admin `GET /diagnostics`, `GET /metrics` |
| Operational metrics | `AegisMetrics` registers architecture §19 set (API, WS, outbox/stream, simulation, ML/provider, agents, snapshot/replay, scoring, approval wait, dependency probe, exporter failures) |
| Secret/PII redaction + label rules | `redaction.py`; `ALLOWED_METRIC_LABELS` / `FORBIDDEN_METRIC_LABELS`; `MetricLabelPolicyV1` |
| Local stack, dashboards, alerts | `infra/observability/**` + compose services `otel-collector`, `tempo`, `prometheus`, `grafana`; dashboard `AEGIS Operations`; `alerts.yml` |
| Web correlation headers | `apps/web/lib/observability/correlation.ts` applied via `auth-fetch.ts` (`traceparent`, `X-Request-Id`, `X-Correlation-Id`, run/incident headers) |
| Fail-open exporters | Exporter failures counted (`aegis.telemetry.exporter.failures`); never raised into domain paths; simulation telemetry isolation tested |
| **AC1** End-to-end tracing by shared IDs | Correlation context + header round-trip tests; frontend W3C `traceparent`; structured logs carry `traceId` / `runId` / `incidentId` |
| **AC2** Logs/traces contain no secrets | Redaction unit tests; collector config strips auth/cookie span attributes; instrumentation strips prompt/token attributes |
| **AC3** Health/readiness machine-readable and distinct | Contract fixtures + `/health`/`/live` vs `/ready` (dependencies only on ready); readiness `503` when required deps fail |
| **AC4** Required operational metrics emitted and tested | Metric registration + label policy tests; WS/streaming bridge tests; provider/sim/approval/replay/scoring/agent instrumentation |

**Explicitly not implemented:** Phase 32 security hardening beyond existing `admin:manage` on diagnostics; Phase 33 production/cloud collector deployment; Phase 34 load/chaos beyond local stack; Phase 35 multi-region; commercial APM procurement; treating telemetry as authoritative state.

### Distinctions (must preserve)

| Distinction | Meaning in this phase |
| ----------- | --------------------- |
| Domain audit vs ops logs | `SecurityAuditEventV1` (Phase 30, authoritative PG) ≠ `StructuredLogRecordV1` / JSON ops logs |
| Authoritative events vs telemetry | Append-only PG events + outbox remain SoR; OTel signals are projections for inspection only |
| Liveness vs readiness | `/health` + `/live` = process alive; `/ready` = required deps available (Postgres, Redis, object storage) |
| Metrics vs traces | Metrics = bounded aggregates with allowlisted labels; traces/logs carry entity IDs and causation |
| Phase 31 vs Phase 32 | Phase 31 = observability surfaces + fail-open telemetry; Phase 32 = broader security hardening (not absorbed) |

**Note:** Compose service `minio` is the approved object-storage stand-in for the Phase 31 validation command name `object-storage`.

## Files added

| Path | Reason |
| ---- | ------ |
| `packages/observability/src/aegis_observability/{setup,context,logging,redaction,metrics,health,instrumentation,middleware}.py` | Shared OTel, context, logs, redaction, metrics, health, instrumentation |
| `packages/contracts-python/src/aegis_contracts/observability.py` | Six observability contracts (Python) |
| `packages/contracts-ts/src/observability.ts` | Six observability contracts (TypeScript) |
| `apps/api/src/aegis_api/observability/**` | `/live`, `/diagnostics`, `/metrics`; readiness builder |
| `apps/web/lib/observability/**` | Frontend correlation helpers + unit test |
| `infra/observability/**` | Collector, Prometheus, Tempo, Grafana, alerts, dashboard |
| `tests/observability/**` | Phase 31 unit/API/ops/WS/simulation isolation tests |
| `tests/contract/fixtures/valid/{telemetry_context,structured_log_record,health_response,ready_response,dependency_status,metric_label_policy}_v1.json` | Contract fixtures |
| `tests/contract/fixtures/schemas/*observability*.schema.json` (+ health/ready/telemetry/log/metric/dependency) | JSON Schema fixtures |
| `docs/observability.md` | Operator/architecture observability docs |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0032-observability.md` | ADR 0032 (Accepted) |
| `docs/handoffs/31-observability-HANDOFF.md` | This handoff |

## Files modified

| Path | Reason |
| ---- | ------ |
| `apps/api/src/aegis_api/main.py` | OTel lifespan; `/health`/`/ready` contracts; mount public + admin-protected ops routers |
| `apps/api/src/aegis_api/approvals/service.py` | Approval wait metrics + actor context merge |
| `apps/api/src/aegis_api/websocket/metrics.py` | Bridge gateway counters into OTel |
| `apps/api/src/aegis_api/auth/deps.py` | Observability-related auth dependency wiring (admin ops) |
| `apps/api/pyproject.toml` | Depend on `aegis-observability` |
| `apps/web/lib/api/auth-fetch.ts` | Apply correlation headers on API fetch |
| `packages/model-provider/.../service.py` | Provider call metrics (latency/tokens/cost/retries) |
| `packages/simulation-domain/.../runtime.py` | Simulation step event metrics (fail-open; no determinism change) |
| `services/replay/.../service.py` | Replay duration/event metrics |
| `services/scoring/.../service.py` | Scoring duration metrics |
| `services/agents/.../runtime/executor.py` | Agent task metrics + context |
| `services/workers/.../outbox/relay_runner.py` | Worker OTel init + outbox unpublished bridge |
| `packages/contracts-*/versioning.py` (+ TS) | Schema versions + `WORKSPACE_VERSION` → `0.0.0-phase31` |
| `packages/contracts-*/__init__` / `index.ts` / `fixtures.py` | Export observability contracts + fixture map |
| `packages/contracts-python/.../settings.py` | OTel / health / log env settings |
| `packages/policy/.../__init__.py` | Workspace version bump |
| `packages/observability/{pyproject.toml,README.md}` | Package deps + usage |
| `docker-compose.yml` | `otel-collector`, `tempo`, `prometheus`, `grafana`; OTLP env on api/worker/simulator; volumes |
| `.env.example` | Observability env defaults |
| `pyproject.toml` / `uv.lock` | Workspace package wiring |
| `tests/contract/fixtures/compatibility-manifest.json` | `workspaceVersion` `0.0.0-phase31` |

## Files removed

None.

## Contracts introduced or changed

Durable cross-language (`schemaVersion` 1 each):

1. `TelemetryContextV1`
2. `StructuredLogRecordV1`
3. `HealthResponseV1`
4. `ReadyResponseV1`
5. `DependencyStatusV1`
6. `MetricLabelPolicyV1`

Supporting enums/constants: `HealthStatusV1`, `ReadyStatusV1`, `DependencyStateV1`, `LogOutcomeV1`, `ActorKindV1`, `MetricTypeV1`, `ALLOWED_METRIC_LABELS`, `FORBIDDEN_METRIC_LABELS`.

`WORKSPACE_VERSION` = `0.0.0-phase31`.

## Migrations, env, fixtures, commands

- **Migrations:** none (observability is non-authoritative; no new durable domain tables).
- **Env** (see `.env.example` / `AegisSettings`):

  | Variable | Default | Role |
  | -------- | ------- | ---- |
  | `OTEL_ENABLED` | `true` | Enable SDK; `false` → noop metrics |
  | `OTEL_SERVICE_NAME` | `aegis-api` | Resource `service.name` |
  | `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Collector |
  | `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | `grpc` or `http/protobuf` |
  | `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Sampler |
  | `OTEL_TRACES_SAMPLER_ARG` | `1.0` | Sample ratio |
  | `OTEL_METRICS_EXPORT_INTERVAL_MS` | `15000` | Export cadence |
  | `OTEL_EXPORTER_FAILURE_MODE` | `ignore` | Fail-open |
  | `AEGIS_LOG_JSON` | `true` | Structured JSON logs |
  | `AEGIS_HEALTH_PROBE_TIMEOUT_MS` | `2000` | Bounded dependency probes |
  | `AEGIS_READY_REQUIRE_REDIS` | `true` | Redis required for readiness |
  | `AEGIS_READY_REQUIRE_OBJECT_STORAGE` | `true` | Object storage required for readiness |
  | `AEGIS_TELEMETRY_RETENTION_HOURS` | `168` | Local retention guidance (7d) |

- **Fixtures:** `tests/contract/fixtures/valid/` + schemas listed above; compatibility manifest bumped.
- **Local observability stack:**

```bash
docker compose up -d postgres redis minio otel-collector tempo prometheus grafana
docker compose up -d api web worker simulator   # or run API via uv locally
# Grafana http://localhost:3001  Prometheus http://localhost:9090  Tempo http://localhost:3200
```

## Tests added

| Test | Proves |
| ---- | ------ |
| `tests/observability/test_observability_core.py` | Contract fixtures; correlation propagation; label allowlist; readiness semantics; redaction; exporter fail-open; JSON logger; idempotent init |
| `tests/observability/test_api_observability.py` | Public `/health`/`/live`; correlation header round-trip; protected `/diagnostics`/`/metrics` require `admin:manage` separation |
| `tests/observability/test_ops_auth.py` | Admin permission dependency factory + unauthenticated mapping |
| `tests/observability/test_ws_and_streaming_telemetry.py` | WS + streaming metric bridges emit OTel counters without replacing domain metrics |
| `tests/observability/test_simulation_telemetry_isolation.py` | Simulation step telemetry does not change event count / determinism |
| `apps/web/lib/observability/correlation.test.ts` | Frontend `traceparent` + correlation headers without secrets |

## Validation commands and results

| Command | Result |
| ------- | ------ |
| `uv run pytest tests/observability -q` | **PASS** — 21 passed, 1 warning (Starlette/httpx TestClient deprecation) |
| `pnpm format:check` | PENDING |
| `pnpm lint` | PENDING |
| `pnpm typecheck` | PENDING |
| `pnpm test` | PENDING (includes web correlation unit test) |
| `pnpm build` | PENDING |
| `pnpm check-contracts` | PENDING |
| `uv run ruff check .` | PENDING |
| `pnpm typecheck:py` / `uv run mypy apps services packages` | PENDING |
| `uv run lint-imports` | PENDING |
| `uv run pytest -q` (full suite) | PENDING |
| `docker compose up -d postgres redis minio` (spec: `object-storage`) | **BLOCKED in this environment** — Docker overlay mount fails (`failed to mount ... fstype: overlay ... err: invalid argument`). Compose service `minio` is the approved stand-in for `object-storage`. |
| `docker compose up -d otel-collector tempo prometheus grafana` | **BLOCKED** — same overlay limitation (confirmed attempting `otel-collector`/`tempo` create) |
| `uv run pytest tests/integration -q` | PENDING (depends on Postgres/Redis/MinIO; compose blocked here) |

Validation agent should re-run the PENDING commands on a host where Docker overlay works.

## Architecture decisions and ADR references

- **ADR 0032 — Observability and OpenTelemetry** — **Accepted** (Phase 31 implementation)
- ADR 0031 preserved — `/diagnostics` and `/metrics` remain behind `admin:manage`; identity never from client-trusted headers
- Existing `StreamingMetrics` / `GatewayMetrics` bridged into OTel rather than replaced as business logic

## Known limitations and deferred work

- **Docker overlay limitation** in the current cloud agent environment may block local compose (Postgres/Redis/MinIO + observability stack). Unit/API observability tests do not require the collector.
- Local sample ratio defaults to `1.0`; production sampling/retention tightening is Phase 33.
- No commercial APM; OSS collector → Tempo/Prometheus/Grafana only.
- Snapshot metric helpers exist in `AegisMetrics`; deeper snapshot-path instrumentation may be extended by dependents as needed.
- Phase 32 security hardening, Phase 33 deploy/ops hardening, Phase 34 resilience/load, Phase 35 multi-region — deliberately deferred.

## Risks and instructions for dependent phases

- Never treat dashboards, metrics, or traces as authoritative domain state; PostgreSQL events/audit remain SoR.
- Preserve fail-open exporters: telemetry failures must not alter simulation determinism, auth, or persistence.
- Keep metric labels on the allowlist; put entity IDs in traces/logs only.
- Keep `/diagnostics` and `/metrics` behind `admin:manage`; do not make diagnostic HTML or metric dumps public.
- Do not log secrets, tokens, cookies, prompts, or credentials as span attributes.
- When extending compose, keep `minio` as the object-storage stand-in unless an ADR renames the service.
- Phase 32+ must not absorb observability redesigns that break the six contracts or ADR 0032 fail-open rules.

## Telemetry inventory

| Service | Logs | Traces | Metrics | Health | Owner |
| ------- | ---- | ------ | ------- | ------ | ----- |
| `aegis-api` | Structured JSON via `aegis_observability.logging` | HTTP middleware + `traced_operation`; OTLP | API, WS bridge, dependency probes, exporter failures | `/health`, `/live`, `/ready`, `/diagnostics` | `apps/api` + `packages/observability` |
| `aegis-web` | N/A (browser) | Correlation headers outbound (`traceparent`, request/correlation/run/incident) | N/A | `apps/web` `/api/health` (workspace version) | `apps/web/lib/observability` |
| `aegis-worker` (outbox relay) | Structured via init | Context bind per batch | Outbox unpublished / lag bridge | Process relies on API readiness model | `services/workers` |
| `aegis-simulator` | Via shared package when wired | Simulation step spans/metrics fail-open | `aegis.simulation.*` | N/A (API readiness covers deps) | `packages/simulation-domain` |
| Model provider | Redacted attrs only | Provider call recording | `aegis.provider.*` | N/A | `packages/model-provider` |
| Agents | Context merge | Task duration spans/metrics | `aegis.agent.*` | N/A | `services/agents` |
| Replay | Fail-open | Replay op metrics | `aegis.replay.*` | N/A | `services/replay` |
| Scoring | Fail-open | Scoring op metrics | `aegis.scoring.*` | N/A | `services/scoring` |
| Approvals | Actor context merge | Approval wait | `aegis.approval.wait` | N/A | `apps/api/approvals` |
| otel-collector | Collector logs | Receives OTLP → Tempo | Prometheus exporter `:8889` | Collector health | `infra/observability` |
| prometheus / tempo / grafana | Infra | Tempo storage | Scrape + dashboards + alerts | Compose healthchecks | `infra/observability` |

## Metric inventory

| Name | Type | Unit | Labels | Description | Source | Cardinality |
| ---- | ---- | ---- | ------ | ----------- | ------ | ----------- |
| `aegis.api.request.duration` | histogram | ms | `service`, `operation`, `status`, `method`, `route_group` | HTTP API request duration | API middleware | low (route_group bounded) |
| `aegis.api.request.errors` | counter | 1 | same | HTTP API errors | API middleware | low |
| `aegis.api.request.count` | counter | 1 | same | HTTP API request count | API middleware | low |
| `aegis.ws.connections` | up_down_counter | 1 | `service`, `operation`, `ws_event`, `status` | Active WebSocket connections | gateway metrics bridge | low |
| `aegis.ws.messages` | counter | 1 | `service`, `operation`, `ws_event`, `status` | WebSocket messages | gateway metrics | low |
| `aegis.ws.delivery_lag` | histogram | ms | `service`, `operation`, `ws_event`, `status` | WS delivery lag | bridge | low |
| `aegis.outbox.delay` | histogram | s | `service`, `operation`, `status` | Outbox publish delay | streaming bridge / worker | low |
| `aegis.outbox.unpublished` | up_down_counter | 1 | `service`, `operation`, `status` | Unpublished outbox rows | streaming bridge / worker | low |
| `aegis.stream.consumer_lag` | up_down_counter | 1 | `service`, `operation`, `status` | Redis stream consumer lag | streaming bridge | low |
| `aegis.event.persist.duration` | histogram | ms | `service`, `operation`, `status` | Event persistence latency | streaming bridge | low |
| `aegis.event.persist.failures` | counter | 1 | allowlisted | Event persistence failures | metrics registry | low |
| `aegis.event.sequence_gaps` | counter | 1 | allowlisted | Detected sequence gaps | metrics registry | low |
| `aegis.worker.queue_depth` | up_down_counter | 1 | allowlisted | Worker queue depth | metrics registry | low |
| `aegis.simulation.events` | counter | 1 | `service`, `operation`, `status` | Simulation events emitted | simulation runtime | low |
| `aegis.simulation.duration` | histogram | ms | allowlisted | Simulation run duration | metrics registry | low |
| `aegis.simulation.completions` | counter | 1 | allowlisted | Completions/failures | metrics registry | low |
| `aegis.ml.inference.duration` | histogram | ms | allowlisted | ML inference latency | metrics registry | low |
| `aegis.provider.request.duration` | histogram | ms | `service`, `operation`, `provider`, `model_alias`, `status` | Provider call latency | model-provider | low (alias bounded) |
| `aegis.provider.request.count` | counter | 1 | same | Provider calls | model-provider | low |
| `aegis.provider.request.retries` | counter | 1 | same | Provider retries | model-provider | low |
| `aegis.provider.tokens` | counter | 1 | same | Token usage | model-provider | low |
| `aegis.provider.cost` | counter | 1 | same | Cost units | model-provider | low |
| `aegis.agent.task.duration` | histogram | ms | `service`, `operation`, `agent_name`, `status` | Agent task duration | agents executor | low |
| `aegis.agent.tool.failures` | counter | 1 | allowlisted | Tool failures | metrics registry | low |
| `aegis.agent.cost` | counter | 1 | allowlisted | Agent cost units | metrics registry | low |
| `aegis.snapshot.duration` | histogram | ms | allowlisted | Snapshot duration | metrics registry | low |
| `aegis.replay.duration` | histogram | ms | `service`, `operation`, `status` | Replay reconstruction | replay service | low |
| `aegis.replay.events` | counter | 1 | allowlisted | Replay event counts | replay service | low |
| `aegis.scoring.duration` | histogram | ms | `service`, `operation`, `status` | Scoring duration | scoring service | low |
| `aegis.approval.wait` | histogram | ms | `service`, `operation`, `status` | Approval wait time | approvals service | low |
| `aegis.dependency.probe.duration` | histogram | ms | `service`, `operation`, `dependency`, `status` | Dependency probe latency | `/ready` / diagnostics | low (3 deps) |
| `aegis.telemetry.exporter.failures` | counter | 1 | `service`, `operation`, `status` | Exporter failures (non-fatal) | observability runtime | low |

Forbidden high-cardinality labels (examples): `user_id`, `event_id`, `request_id`, `trace_id`, `run_id`, `incident_id`, `prompt`, `url`, `error_message`, `session_id`, `actor_id`.

## Dashboard inventory

Dashboard: Grafana **AEGIS Operations** (`infra/observability/grafana/dashboards/aegis-operations.json`, uid `aegis-operations`).

| Panel | Datasource | Question answered |
| ----- | ---------- | ----------------- |
| API request rate | Prometheus | Are we receiving traffic? |
| API error rate | Prometheus | Is the API failing at rate? |
| API request duration (p95) | Prometheus | How slow are HTTP requests? |
| WebSocket connections & messages | Prometheus | Is realtime delivery healthy? |
| Simulation & event throughput | Prometheus | Are sim events flowing; is consumer lag rising? |
| Model provider & agent latency | Prometheus | Are LLM/agent paths slow? |
| Dependency probe latency | Prometheus | Which dependency is slow (postgres/redis/object storage)? |
| Replay, scoring, approval wait | Prometheus | Are post-run / human-in-loop paths delayed? |
| Telemetry exporter failures | Prometheus | Is observability itself failing (non-fatal)? |
| Traces (Explore → Tempo note) | Tempo (via Explore) | Can we follow an incident end-to-end by shared IDs? |

Alerts (`infra/observability/alerts.yml`): `AegisApiHighErrorRate`, `AegisOutboxLag`, `AegisTelemetryExporterFailures`.

## Evidence for every acceptance criterion

| AC | Evidence |
| -- | -------- |
| AC1 — Representative incidents traced end-to-end by shared IDs | `TelemetryContextV1` + header propagation (`test_correlation_context_propagation`, `test_correlation_headers_round_trip`, web `correlation.test.ts`); logs carry `traceId`/`runId`/`incidentId`; Tempo Explore guidance in dashboard + `docs/observability.md` |
| AC2 — Logs/traces contain no secrets | `test_redaction_of_credentials_and_sensitive_fields`; `redaction.py`; collector attribute processor; instrumentation strips prompt/token/auth attributes |
| AC3 — Health/readiness machine-readable and distinct | Fixtures `health_response_v1` vs `ready_response_v1`; `test_health_and_ready_fixtures_distinct`; `test_liveness_is_public_and_machine_readable`; `test_readiness_semantics`; `/ready` returns `503`/`not_ready` when required deps fail |
| AC4 — Required operational metrics emitted and tested | `AegisMetrics` registration; `test_metric_labels_reject_unbounded`; `test_metric_registration_noop`; `test_websocket_metrics_emit_otel_counters`; instrumentation hooks in provider/sim/approvals/replay/scoring/agents/worker |

## Confirmation: no prohibited shortcut used

Production-path observability is implemented in `packages/observability` and wired through API routes, middleware, workers, and domain hooks — not scaffolding-only stubs. Exporters fail open and do not break core behavior. Secrets are redacted; high-cardinality IDs are forbidden on metric labels. Diagnostics remain `admin:manage`-protected (Phase 30). Telemetry is not treated as authoritative state. Existing domain metrics (`StreamingMetrics` / `GatewayMetrics`) were bridged, not deleted or weakened. Tests were added rather than loosened. Phase 32–35 scope was not absorbed. Validation commands not executed in this environment are marked PENDING/BLOCKED; only `tests/observability` (21 passed) and the Docker overlay failure are claimed as observed results.
