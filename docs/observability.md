# AEGIS Observability (Phase 31)

Observability inspects and explains system behavior. It is **not** authoritative
domain state. PostgreSQL events, audit records, replay artifacts, and domain
data remain the system of record.

## Architecture

```text
apps/web  --traceparent/X-Request-Id-->  apps/api
apps/api / workers / simulator / agents
        |  aegis_observability (context, logs, metrics, traces, health)
        v
   OTLP (gRPC :4317 / HTTP :4318)
        v
  otel-collector --> Tempo (traces) + Prometheus exporter (:8889)
        v
  Grafana (dashboards) + Prometheus (scrape + alert examples)
```

Shared package: `packages/observability` (`aegis_observability`).
API wiring: `apps/api/src/aegis_api/observability/`.
Frontend correlation: `apps/web/lib/observability/`.
Infra: `infra/observability/`.

## OpenTelemetry initialization

Call `init_observability(...)` once per process (API lifespan, worker entry):

| Env | Default | Meaning |
|---|---|---|
| `OTEL_ENABLED` | `true` | Enable SDK; `false` uses noop metrics |
| `OTEL_SERVICE_NAME` | `aegis-api` | Resource `service.name` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Collector |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | `grpc` or `http/protobuf` |
| `OTEL_TRACES_SAMPLER_ARG` | `1.0` | ParentBasedTraceIdRatio |
| `OTEL_METRICS_EXPORT_INTERVAL_MS` | `15000` | Export cadence |
| `AEGIS_LOG_JSON` | `true` | Structured JSON logs |
| `AEGIS_HEALTH_PROBE_TIMEOUT_MS` | `2000` | Bounded dependency probes |
| `AEGIS_READY_REQUIRE_REDIS` | `true` | Redis required for readiness |
| `AEGIS_READY_REQUIRE_OBJECT_STORAGE` | `true` | Object storage required for readiness |
| `AEGIS_TELEMETRY_RETENTION_HOURS` | `168` | Local retention guidance (7d) |

Exporter failures are wrapped fail-open: counted, logged, never raised into domain paths.

## Collector and exporters

Local compose services: `otel-collector`, `tempo`, `prometheus`, `grafana`.

- Collector receives OTLP, redacts auth/cookie span attributes, batches, exports traces to Tempo and metrics to a Prometheus exporter.
- Prometheus scrapes `otel-collector:8889` and loads `infra/observability/alerts.yml`.
- Grafana provisions Prometheus + Tempo datasources and the AEGIS Operations dashboard.

## Trace and span naming

- HTTP: `HTTP {METHOD} {route_group}`
- Domain helpers: `traced_operation(operation=...)` uses the operation name
- Attributes use `aegis.*` prefixes for domain IDs when cardinality is controlled
- Entity IDs belong in traces/logs, **not** metric labels

## Correlation context

`TelemetryContext` / `TelemetryContextState` fields:

`traceId`, `spanId`, `correlationId`, `requestId`, `runId`, `incidentId`,
`agentSessionId`, `eventSequence`, `service`, `operation`, `actorId`,
`actorKind`, `actorRole`, `outcome`, `durationMs`

Propagation headers: `traceparent`, `X-Request-Id`, `X-Correlation-Id`,
`X-Aegis-Run-Id`, `X-Aegis-Incident-Id`.

Frontend `apiFetch` applies correlation headers automatically.

## Structured log schema

Production logs are JSON records matching `StructuredLogRecordV1`
(`schemaVersion`, `timestamp`, `level`, `message`, correlation fields,
`service`, `operation`, `outcome`, `durationMs`, `errorKind`, `attributes`).

Levels follow `LOG_LEVEL` (`debug|info|warn|error`).

## Metrics and label conventions

Allowed labels: `service`, `operation`, `status`, `outcome`, `provider`,
`model_alias`, `agent_name`, `dependency`, `method`, `route_group`,
`error_kind`, `ws_event`.

Forbidden (unbounded): user/event/request/trace/run/incident IDs, prompts,
URLs, error messages, session/actor IDs.

See metric inventory in the Phase 31 handoff.

## Health, liveness, readiness

| Endpoint | Auth | Meaning |
|---|---|---|
| `GET /health` | public | Liveness — process alive |
| `GET /live` | public | Explicit liveness alias (machine-readable contract) |
| `GET /ready` | public | Readiness — required deps available (Postgres, Redis, object storage) |
| `GET /diagnostics` | `admin:manage` | Dependency detail + metric bridges |
| `GET /metrics` | `admin:manage` | Operational metrics text snapshot |

Readiness returns `503` with `status=not_ready` when a required dependency fails.
Probes are bounded by `AEGIS_HEALTH_PROBE_TIMEOUT_MS` and do not cascade.

**Liveness ≠ readiness.** Domain audit records ≠ operational logs.
Authoritative events ≠ telemetry. Metrics ≠ traces.

## Dashboards and alerting

- Dashboard: Grafana `AEGIS Operations` (`infra/observability/grafana/dashboards/aegis-operations.json`)
- Alerts: `infra/observability/alerts.yml` (API error rate, outbox lag, exporter failures)
- Local Grafana: `http://localhost:3001` (anonymous viewer; admin/`aegis_dev` for edits)

## Sampling and retention

- Local default sample ratio `1.0` for development/demo.
- Prometheus retention `--storage.tsdb.retention.time=7d`.
- Tempo block retention `168h`.
- Production should lower sample rates and tighten retention via env (Phase 33).

## Redaction

`aegis_observability.redaction` strips passwords, tokens, cookies,
`Authorization`, API keys, and sensitive key names from logs/headers/mappings.
Model prompts and credentials must not be exported as span attributes.

## Telemetry failure behavior

Collector/exporter failure:

- does **not** corrupt domain persistence
- does **not** bypass auth
- does **not** alter deterministic simulation results
- increments `aegis.telemetry.exporter.failures` and emits a structured warning

## Local development

```bash
docker compose up -d postgres redis minio otel-collector tempo prometheus grafana
docker compose up -d api web worker simulator   # or run API via uv locally
# Grafana http://localhost:3001  Prometheus http://localhost:9090  Tempo http://localhost:3200
```

Note: compose service `minio` is the approved stand-in for the Phase 31
validation command’s `object-storage` name.

## Production configuration boundaries

- Never enable noop health success.
- Keep diagnostic routes behind `admin:manage`.
- Do not place secrets in telemetry.
- Do not treat dashboards as authoritative state.
- Phase 32 hardens security further; Phase 33 deploys cloud collectors.

## Distinctions Phases 32–35 must preserve

- Domain audit (`SecurityAuditEventV1`) vs operational structured logs
- Authoritative PG events vs OTel signals
- Liveness vs readiness
- Metrics (aggregates) vs traces (per-request causation)
- Phase 31 observability vs Phase 32 security hardening
