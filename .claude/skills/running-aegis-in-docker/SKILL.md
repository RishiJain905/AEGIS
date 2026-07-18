---
name: running-aegis-in-docker
description: Use when asked to run, start, launch, deploy, or test the AEGIS app — locally or via Docker — or when an api/web/worker container in this repo fails to start, crashes on boot, or shows unhealthy in `docker compose ps`.
---

# Running AEGIS in Docker

## Overview

AEGIS is a pnpm+uv monorepo with a Docker Compose stack: postgres, redis,
minio, api, web, worker, simulator, plus an observability quartet
(otel-collector, tempo, prometheus, grafana). The api/web images build from
source; Alembic migrations run from the **host**, not in a container —
`alembic` is a dev-only dependency and isn't installed in any image.

## Quick start

```bash
cp .env.example .env                       # AEGIS_PROVIDER_DEFAULT=mock by default — no API keys needed
docker compose up -d postgres redis minio   # wait for "healthy" (docker compose ps)
uv sync --frozen --all-packages             # installs alembic + workspace packages locally
uv run alembic upgrade head                 # migrations run from host against localhost:5432
docker compose up -d --build                # full stack: api, web, worker, simulator, observability
```

Web UI: http://localhost:3000 · API: http://localhost:8000 · Grafana: http://localhost:3001

## Known gotchas

- **`ModuleNotFoundError: No module named 'aegis_api'`, api container exits.**
  `apps/api/Dockerfile`'s builder stage must `COPY apps/api/src apps/api/src`
  *before* `RUN uv sync --frozen --no-dev --package aegis-api`. Every other
  workspace package's `src/` is copied before its own `uv sync`; if api's
  copy regresses back to runner-stage-only, `uv sync` builds an editable
  install with no source present, producing a dist-info with no `.pth`/module
  files. Check with:
  `docker run --rm --entrypoint sh aegis-api -c "find /app/.venv/lib/python3.12/site-packages -iname '*aegis_api*'"`
  — must show `_editable_impl_aegis_api.pth`, not just `aegis_api-0.0.0.dist-info`.
- **`web` container stuck "unhealthy" despite responding fine on `curl localhost:3000`.**
  Docker auto-sets `HOSTNAME` to the container ID; Next.js standalone's
  `server.js` binds to `process.env.HOSTNAME` instead of all interfaces, so
  the in-container healthcheck (`wget http://127.0.0.1:3000`) can't connect.
  Fixed via `HOSTNAME: '0.0.0.0'` under `web.environment` in
  `docker-compose.yml` — if it regresses, that's the first thing to check.
- **`simulator` container exits immediately (exit code 2).** By design, not a
  bug — `aegis-simulator` is a one-shot CLI (`run`, `run-persisted`,
  `determinism-check`, ...), not a daemon, and nothing else depends on it.
  Invoke on demand: `docker compose run simulator run --scenario scenarios/<name> --seed 42 --steps 50`.

## Testing the running stack (auth + mock provider)

Phase 30 auth locks every `/api/v1/*` route except `/health`, `/ready`, and
the auth routes themselves. Dev login is enabled via `AEGIS_DEV_AUTH_ENABLED=true`:

```bash
curl http://localhost:8000/api/v1/auth/dev/users   # seeded identities (same list the web /sign-in page renders)

curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/dev/login \
  -H "Content-Type: application/json" -d '{"userId":"user:admin-alpha"}'
# response body includes session.csrfToken — required as X-CSRF-Token header on POST/PUT/DELETE, cookie alone isn't enough

curl -b cookies.txt -H "X-CSRF-Token: <csrfToken>" http://localhost:8000/api/v1/providers/config
# confirms "defaultProvider":"mock"
```

Web UI: open http://localhost:3000/sign-in and click any dev identity button
— no password, redirects to `/` on success.

Runtime IDs (`traceId`, `requestId`, ...) must match
`^(prefix)_[0-9A-HJKMNP-TV-Z]{26}$` (Crockford base32, excludes I/L/O/U) —
e.g. `trc_` + 26 chars, `gen_` + 26 chars — or contract validation rejects the
request with `INVALID_IDENTIFIER`.
