# ADR 0032: Observability and OpenTelemetry

## Status

Accepted (Phase 31 implementation)

## Context

Architecture §19 and Phase 31 require OpenTelemetry-compatible logs, traces, and
metrics across API, workers, simulation, providers, agents, replay, and
approvals. Prior phases shipped in-memory counters and HTML harnesses only.
Telemetry must not become authoritative state and must not break domain
behavior on exporter failure. Phase 30 already protects diagnostic HTML pages
with `admin:manage`.

## Decision

1. **Shared package** `aegis_observability` owns OTel init, correlation context,
   structured JSON logging, redaction, bounded metric registration, and
   dependency health probes. Apps/services call helpers; they do not reimplement
   exporters.
2. **Local OSS stack**: OpenTelemetry Collector + Prometheus + Grafana + Tempo.
   No commercial APM procurement.
3. **Fail-open exporters**: OTLP export failures are counted and logged; they
   never raise into domain paths or alter simulation determinism.
4. **Metric label allowlist** with explicit forbidden high-cardinality labels.
   Entity IDs stay in traces/logs.
5. **Distinct health surfaces**: public liveness (`/health`, `/live`), public
   readiness (`/ready` with bounded Postgres/Redis/object-storage probes), and
   admin-only diagnostics (`/diagnostics`, `/metrics`).
6. **Contracts** `TelemetryContextV1`, `StructuredLogRecordV1`,
   `HealthResponseV1`, `ReadyResponseV1`, `DependencyStatusV1`,
   `MetricLabelPolicyV1` live in the shared contracts packages.
7. **Authorization**: protected operational endpoints continue to require
   Phase 30 `admin:manage`; identity is never taken from client-trusted headers.

## Consequences

- Compose gains observability services for local demos and validation.
- Existing `StreamingMetrics` / `GatewayMetrics` remain and are bridged into
  OTel rather than replaced as business logic.
- Phases 32–35 must preserve fail-open telemetry, label policy, auth on
  diagnostics, and the non-authoritative role of observability data.

## References

- `docs/architecture.md` §19
- `docs/AEGIS-v1.0-Agent-Specs/production-readiness/31-observability.md`
- ADR 0031 — Authentication and Authorization
- `docs/observability.md`
