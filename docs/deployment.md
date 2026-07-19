# AEGIS deployment contract

This document is the Phase 33 deployment-readiness contract. It describes the
production shape without provisioning cloud resources or activating a deploy
workflow. ADR 0033 is authoritative: the local production-like Compose stack
is the validation stand-in, and cloud activation requires a separate owner-
approved task.

## Local production-shaped stack

The development stack remains the default and keeps dev authentication and
local fixture behavior usable:

```bash
docker compose -f docker-compose.yml config --quiet
docker compose up -d postgres redis minio
```

For the production-shaped rehearsal, copy the fake example to an ignored local
env file, then use the override. The values in the example are not credentials
and must never be promoted to a cloud environment.

```bash
cp .env.production.example .env.production
export AEGIS_PROD_ENV_FILE=.env.production
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml build api web worker simulator
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
uv run python scripts/deploy_smoke_test.py --environment local \
  --env-file .env.production
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml down
```

On Windows PowerShell, set `$env:AEGIS_PROD_ENV_FILE='.env.production'` for
Compose interpolation. The overlay binds the local rehearsal to loopback
ports 18000 (API), 13000 (web), 55432 (PostgreSQL), and 56379 (Redis); these
host ports are intentionally separate from the development stack.

The overlay includes a one-shot `migrate` service. API, worker, and simulator
containers wait for it to complete successfully. The API image carries
`alembic.ini` and `migrations/` solely so this local job matches the future
managed migration-job boundary.

## Environment-variable contract

`required` means required by the service in the named mode. `secret` means the
value must come from a secret manager or injected secret file in a hosted
environment; a local example value is never a production credential. Defaults
below refer to `.env.example` unless noted.

### Runtime, data, and ports

| Name                        | Service                           | Required          | Default/example               | Secret                   | Owner         |
| --------------------------- | --------------------------------- | ----------------- | ----------------------------- | ------------------------ | ------------- |
| `AEGIS_ENV`                 | API, worker, simulator, migration | yes               | `development`                 | no                       | Phase 00 / 33 |
| `LOG_LEVEL`                 | API, worker, simulator            | no                | `info`                        | no                       | Phase 00      |
| `POSTGRES_HOST`             | API, worker, simulator, migration | yes in production | `localhost`                   | no                       | Phase 02 / 33 |
| `POSTGRES_PORT`             | API, worker, simulator, migration | yes               | `5432`                        | no                       | Phase 02      |
| `POSTGRES_DB`               | API, worker, simulator, migration | yes               | `aegis`                       | no                       | Phase 02      |
| `POSTGRES_USER`             | API, worker, simulator, migration | yes               | `aegis`                       | no                       | Phase 02      |
| `POSTGRES_PASSWORD`         | API, worker, simulator, migration | yes               | `aegis_dev`                   | yes                      | Phase 02 / 32 |
| `REDIS_URL`                 | API, worker, simulator            | yes in production | `redis://localhost:6379/0`    | yes when it carries auth | Phase 11 / 33 |
| `S3_ENDPOINT`               | API, worker, simulator            | yes in production | `http://localhost:9000`       | no                       | Phase 02 / 33 |
| `S3_ACCESS_KEY`             | API, worker, simulator, MinIO     | yes in production | `aegis`                       | yes                      | Phase 02 / 33 |
| `S3_SECRET_KEY`             | API, worker, simulator, MinIO     | yes in production | `aegis_dev_secret`            | yes                      | Phase 02 / 33 |
| `S3_BUCKET`                 | API, worker, simulator            | yes               | `aegis-artifacts`             | no                       | Phase 02      |
| `API_PORT`                  | API                               | no                | `8000`                        | no                       | Phase 00 / 33 |
| `WEB_PORT`                  | web                               | no                | `3000`                        | no                       | Phase 00 / 33 |
| `AEGIS_API_HOST_PORT`       | local Compose only                | no                | `18000` in production example | no                       | Phase 33      |
| `AEGIS_WEB_HOST_PORT`       | local Compose only                | no                | `13000` in production example | no                       | Phase 33      |
| `AEGIS_SMOKE_POSTGRES_PORT` | local smoke only                  | no                | `55432` in production example | no                       | Phase 33      |
| `AEGIS_LOCAL_URL`           | local smoke only                  | no                | `http://127.0.0.1:8000`       | no                       | Phase 33      |
| `AEGIS_LOCAL_WS_URL`        | local smoke only                  | no                | derived from local API URL    | no                       | Phase 33      |

### Web public configuration

These values are public configuration and may be embedded in the Next.js
artifact. They must not contain tokens, private URLs, or credentials.

| Name                                 | Service           | Required       | Default/example                      | Secret | Owner         |
| ------------------------------------ | ----------------- | -------------- | ------------------------------------ | ------ | ------------- |
| `NEXT_PUBLIC_AEGIS_DATA_SOURCE`      | web               | no             | `fixture`                            | no     | Phase 04 / 33 |
| `NEXT_PUBLIC_API_BASE_URL`           | web build/runtime | no             | `http://localhost:8000`              | no     | Phase 04 / 33 |
| `NEXT_PUBLIC_WS_URL`                 | web build/runtime | no             | `ws://localhost:8000/ws/v1/realtime` | no     | Phase 12 / 33 |
| `NEXT_PUBLIC_AEGIS_WS_TOKEN`         | web               | no, deprecated | empty                                | no     | Phase 12 / 30 |
| `NEXT_PUBLIC_AEGIS_CSRF_COOKIE_NAME` | web               | no             | `aegis_csrf`                         | no     | Phase 30      |

### Authentication and authorization

Production startup rejects development auth, wildcard CORS, missing OIDC
values, and the placeholder localhost values listed in
`apps/api/src/aegis_api/security/startup.py`.

| Name                         | Service | Required                 | Default/example                    | Secret | Owner         |
| ---------------------------- | ------- | ------------------------ | ---------------------------------- | ------ | ------------- |
| `AEGIS_DEV_AUTH_ENABLED`     | API     | no                       | `true` locally; `false` production | no     | Phase 30      |
| `AEGIS_SESSION_COOKIE_NAME`  | API/web | no                       | `aegis_session`                    | no     | Phase 30      |
| `AEGIS_CSRF_COOKIE_NAME`     | API/web | no                       | `aegis_csrf`                       | no     | Phase 30      |
| `AEGIS_CSRF_HEADER_NAME`     | API/web | no                       | `X-CSRF-Token`                     | no     | Phase 30      |
| `AEGIS_SESSION_TTL_SECONDS`  | API     | no                       | `28800`                            | no     | Phase 30      |
| `AEGIS_CORS_ALLOWED_ORIGINS` | API     | yes in production        | localhost origins locally          | no     | Phase 30      |
| `AEGIS_OIDC_ENABLED`         | API     | yes in production        | `false` locally                    | no     | Phase 30      |
| `AEGIS_OIDC_ISSUER`          | API     | yes when OIDC is enabled | empty locally                      | no     | Phase 30      |
| `AEGIS_OIDC_CLIENT_ID`       | API     | yes when OIDC is enabled | empty locally                      | no     | Phase 30      |
| `AEGIS_OIDC_CLIENT_SECRET`   | API     | yes when OIDC is enabled | empty locally                      | yes    | Phase 30      |
| `AEGIS_OIDC_REDIRECT_URI`    | API     | yes when OIDC is enabled | localhost callback                 | no     | Phase 30 / 33 |
| `AEGIS_OIDC_SCOPES`          | API     | no                       | `openid profile email`             | no     | Phase 30      |
| `AEGIS_WEB_BASE_URL`         | API     | yes in production        | `http://localhost:3000`            | no     | Phase 30 / 33 |

### OpenTelemetry and operations

| Name                                 | Service                | Required | Default/example            | Secret | Owner         |
| ------------------------------------ | ---------------------- | -------- | -------------------------- | ------ | ------------- |
| `OTEL_ENABLED`                       | API, worker, simulator | no       | `true`                     | no     | Phase 31      |
| `OTEL_SERVICE_NAME`                  | API, worker, simulator | no       | `aegis-api`                | no     | Phase 31      |
| `OTEL_EXPORTER_OTLP_ENDPOINT`        | API, worker, simulator | no       | `http://localhost:4317`    | no     | Phase 31      |
| `OTEL_EXPORTER_OTLP_PROTOCOL`        | API, worker, simulator | no       | `grpc`                     | no     | Phase 31      |
| `OTEL_TRACES_SAMPLER`                | API                    | no       | `parentbased_traceidratio` | no     | Phase 31      |
| `OTEL_TRACES_SAMPLER_ARG`            | API                    | no       | `1.0`                      | no     | Phase 31      |
| `OTEL_METRICS_EXPORT_INTERVAL_MS`    | API                    | no       | `15000`                    | no     | Phase 31      |
| `OTEL_EXPORTER_FAILURE_MODE`         | API                    | no       | `ignore`                   | no     | Phase 31      |
| `AEGIS_HEALTH_PROBE_TIMEOUT_MS`      | API                    | no       | `2000`                     | no     | Phase 31      |
| `AEGIS_READY_REQUIRE_REDIS`          | API                    | no       | `true`                     | no     | Phase 31      |
| `AEGIS_READY_REQUIRE_OBJECT_STORAGE` | API                    | no       | `true`                     | no     | Phase 31      |
| `AEGIS_LOG_JSON`                     | API, worker, simulator | no       | `true`                     | no     | Phase 31      |
| `AEGIS_TELEMETRY_RETENTION_HOURS`    | API/telemetry          | no       | `168`                      | no     | Phase 31 / 33 |

### Phase 32 trust-boundary settings

These settings are mandatory parts of the production contract and must not be
dropped when a provider-specific manifest is generated.

| Name                                   | Service                     | Required | Default/example                      | Secret | Owner         |
| -------------------------------------- | --------------------------- | -------- | ------------------------------------ | ------ | ------------- |
| `AEGIS_REQUEST_BODY_MAX_BYTES`         | API                         | no       | `1048576`                            | no     | Phase 32      |
| `AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE` | API                         | no       | `120`                                | no     | Phase 32      |
| `AEGIS_RATE_LIMIT_BURST`               | API                         | no       | `30`                                 | no     | Phase 32      |
| `AEGIS_RATE_LIMIT_MAX_BUCKETS`         | API                         | no       | `10000`                              | no     | Phase 32      |
| `AEGIS_SECURITY_HSTS_ENABLED`          | API                         | no       | `false` until HTTPS edge             | no     | Phase 32 / 33 |
| `AEGIS_SECURITY_HSTS_MAX_AGE_SECONDS`  | API                         | no       | `31536000`                           | no     | Phase 32      |
| `AEGIS_PROVIDER_EGRESS_ALLOWLIST`      | API/agent provider adapters | no       | OpenAI/local bases in `.env.example` | no     | Phase 32      |

### Worker, model-provider, and WebSocket settings

| Name                                           | Service    | Required                   | Default/example                    | Secret | Owner         |
| ---------------------------------------------- | ---------- | -------------------------- | ---------------------------------- | ------ | ------------- |
| `AEGIS_WORKER_MODE`                            | worker     | no                         | `outbox-relay`                     | no     | Phase 11      |
| `AEGIS_PROVIDER_DEFAULT`                       | API/agents | no                         | `mock`                             | no     | Phase 18      |
| `AEGIS_PROVIDER_TIMEOUT_SECONDS`               | API/agents | no                         | `60`                               | no     | Phase 18      |
| `AEGIS_PROVIDER_MAX_RETRIES`                   | API/agents | no                         | `3`                                | no     | Phase 18      |
| `AEGIS_PROVIDER_RETRY_BACKOFF_SECONDS`         | API/agents | no                         | `1`                                | no     | Phase 18      |
| `AEGIS_PROVIDER_CIRCUIT_BREAKER_THRESHOLD`     | API/agents | no                         | `5`                                | no     | Phase 18      |
| `AEGIS_PROVIDER_CIRCUIT_BREAKER_RESET_SECONDS` | API/agents | no                         | `60`                               | no     | Phase 18      |
| `AEGIS_PROVIDER_MAX_CONCURRENT_REQUESTS`       | API/agents | no                         | `10`                               | no     | Phase 18      |
| `AEGIS_PROVIDER_MAX_OUTPUT_TOKENS`             | API/agents | no                         | `4096`                             | no     | Phase 18      |
| `AEGIS_PROVIDER_RECORDED_FIXTURES_DIR`         | API/agents | no                         | `fixtures/model-responses`         | no     | Phase 18      |
| `AEGIS_PROVIDER_OPENAI_API_KEY`                | API/agents | no for mock                | empty                              | yes    | Phase 18 / 32 |
| `AEGIS_PROVIDER_OPENAI_BASE_URL`               | API/agents | no                         | `https://api.openai.com/v1`        | no     | Phase 18      |
| `AEGIS_PROVIDER_OPENAI_MODEL`                  | API/agents | no                         | `gpt-4o-mini`                      | no     | Phase 18      |
| `AEGIS_PROVIDER_LOCAL_BASE_URL`                | API/agents | no                         | `http://localhost:8080/v1`         | no     | Phase 18      |
| `AEGIS_PROVIDER_LOCAL_API_KEY`                 | API/agents | no                         | `llama-cpp`                        | yes    | Phase 18      |
| `AEGIS_PROVIDER_LOCAL_MODEL`                   | API/agents | no                         | `local-model`                      | no     | Phase 18      |
| `AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS`           | API/agents | no                         | `false`                            | no     | Phase 18      |
| `AEGIS_WS_PATH`                                | API/web    | no                         | `/ws/v1/realtime`                  | no     | Phase 12      |
| `AEGIS_WS_ENABLED`                             | API        | no                         | `true`                             | no     | Phase 12      |
| `AEGIS_WS_MAX_CONNECTIONS`                     | API        | no                         | `1000`                             | no     | Phase 12      |
| `AEGIS_WS_MAX_QUEUE_DEPTH`                     | API        | no                         | `256`                              | no     | Phase 12      |
| `AEGIS_WS_MAX_MESSAGE_BYTES`                   | API        | no                         | `65536`                            | no     | Phase 12 / 32 |
| `AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS`          | API        | no                         | `15`                               | no     | Phase 12      |
| `AEGIS_WS_IDLE_TIMEOUT_SECONDS`                | API        | no                         | `45`                               | no     | Phase 12      |
| `AEGIS_WS_DEV_AUTH_ENABLED`                    | API        | no                         | `true` locally; `false` production | no     | Phase 30      |
| `AEGIS_WS_DEV_AUTH_TOKEN`                      | API        | no, disabled in production | `aegis-dev-token`                  | yes    | Phase 12 / 30 |
| `AEGIS_WS_GATEWAY_CONSUMER_GROUP`              | API        | no                         | `aegis-ws-gateway`                 | no     | Phase 12      |
| `AEGIS_WS_SNAPSHOT_GAP_THRESHOLD`              | API        | no                         | `500`                              | no     | Phase 12      |

## Image and artifact contract

Every service image is built from its checked-in multi-stage Dockerfile:

| Role      | Local image tag                 | Hosted artifact contract                             |
| --------- | ------------------------------- | ---------------------------------------------------- |
| API       | `aegis-api:phase33-local`       | `aegis-api:<release>-<gitsha>@sha256:<digest>`       |
| web       | `aegis-web:phase33-local`       | `aegis-web:<release>-<gitsha>@sha256:<digest>`       |
| worker    | `aegis-worker:phase33-local`    | `aegis-worker:<release>-<gitsha>@sha256:<digest>`    |
| simulator | `aegis-simulator:phase33-local` | `aegis-simulator:<release>-<gitsha>@sha256:<digest>` |

Hosted rollouts use immutable release-plus-commit tags and digests; `latest`
is not a production pin. The build record contains the Git revision, Dockerfile,
base-image digests, lockfile revisions, image digest, CycloneDX SBOM reference,
and scan results. Phase 33 CI only builds these artifacts and uploads metadata;
it does not log in, push, publish, or deploy.

Migrations are a separately reviewable artifact from the API image. The
expected local migration head is `013_auth_identity`. Durable event and API
contracts retain their existing schema versions; deployment metadata does not
change domain source-of-truth rules.

## Probe contract

| Probe                           | Expected behavior                                                                         | Guidance                                                                  |
| ------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| API `/health`                   | `200`, `{"status":"ok"}`; liveness only                                                   | initial delay 20s, timeout 5s, 6 retries                                  |
| API `/live`                     | `200`, schema-versioned liveness payload                                                  | public liveness alias; no dependency check                                |
| API `/ready`                    | `200` only when required PostgreSQL, Redis, and object storage are ready; otherwise `503` | probe every 10s with a bounded 2s dependency timeout                      |
| web `/api/health`               | `200`, web status payload                                                                 | initial delay 20s, timeout 5s, 3 retries                                  |
| worker container healthcheck    | import and report worker health                                                           | no public HTTP port; restart on failure                                   |
| simulator container healthcheck | import and report simulator health                                                        | managed service loop in Compose; run jobs separately in hosted deployment |
| WebSocket `/ws/v1/realtime`     | HTTP upgrade `101`; then require the Phase 30 ticket/session handshake                    | reachability is not authorization                                         |

Readiness is the rollout gate. Liveness must stay cheap and must not restart a
healthy process because a dependency is temporarily unavailable.

## Resource and capacity guidance

These are starting points, not autoscaling promises. Measure against the Phase
34 validation workload before increasing replicas.

| Service        | Small load         | Medium load     | Notes                                               |
| -------------- | ------------------ | --------------- | --------------------------------------------------- |
| API            | 0.5 CPU / 512 MiB  | 2 CPU / 1 GiB   | scale stateless replicas behind the HTTPS edge      |
| web            | 0.25 CPU / 256 MiB | 1 CPU / 768 MiB | Next standalone server; public assets are immutable |
| worker         | 0.25 CPU / 256 MiB | 1 CPU / 768 MiB | bound queue concurrency and egress                  |
| simulator      | 0.25 CPU / 256 MiB | 1 CPU / 768 MiB | per-run job isolation is a future provider decision |
| PostgreSQL     | 1 CPU / 1 GiB      | 2 CPU / 4 GiB   | authoritative state; private network and backups    |
| Redis          | 0.25 CPU / 256 MiB | 1 CPU / 512 MiB | stream/cache projection, never sole source of truth |
| object storage | 0.25 CPU / 512 MiB | 1 CPU / 1 GiB   | private artifacts, checksums, versioning            |
| telemetry      | 0.25 CPU / 512 MiB | 1 CPU / 1 GiB   | fail-open exporters and bounded retention           |

## Networking, TLS, and secrets

- The public path is `HTTPS edge -> web/API runtime`. TLS terminates at the
  edge, HTTP is redirected or rejected, and `AEGIS_SECURITY_HSTS_ENABLED` is
  enabled only after the edge certificate and redirect behavior are verified.
- PostgreSQL, Redis, and object storage are private data services. Only the
  runtime network can reach them; worker/provider egress is restricted to an
  explicit allowlist.
- Hosted CORS contains explicit HTTPS web origins. No wildcard CORS, public
  database, public Redis, or public object bucket is part of the target shape.
- Secret manager references are injected at runtime. Browser bundles contain no
  private keys, provider keys, database URLs with passwords, or session tokens.
- Remote Terraform state is documentation-only in Phase 33. A future activation
  task must choose encrypted, locked state and must keep credentials outside
  Terraform source and state wherever the provider supports it.

The unresolved cloud concerns—provider IAM, managed-service behavior, DNS,
certificate issuance, and real backup durability—are deliberately deferred and
tracked in `docs/runbooks/deploy.md` and the Phase 33 handoff.
