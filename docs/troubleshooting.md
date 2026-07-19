# AEGIS Troubleshooting

These checks apply to the local development and production-like Compose stacks. Keep
the failing command, container name, run ID, and timestamp with any report.

## Docker service is unhealthy

Inspect the service and its recent logs:

```powershell
docker compose ps -a
docker compose logs --tail 200 api worker postgres redis
docker inspect --format '{{json .State.Health}}' (docker compose ps -q api)
```

Confirm Docker Desktop is running, the required ports are free, and `.env` contains the
local values from `.env.example`. Restart only the affected local service after fixing
the cause. Do not treat an unhealthy service as a release-validation pass.

## Migration errors

Check the current head and database logs:

```powershell
uv run alembic current
uv run alembic heads
docker compose logs --tail 200 postgres
```

Run `uv run alembic upgrade head` against the intended local database. If the database
contains an incompatible development schema, preserve the logs and database state
before rebuilding it; do not stamp a revision to hide a failed migration.

## Provider unavailable

The default provider is `mock` and does not require network access or model credentials.
Check `AEGIS_PROVIDER_DEFAULT` and run:

```powershell
uv run python scripts/run_provider_harness.py
uv run pytest tests/agents/provider-conformance -q
```

For `openai` or `openai-compatible`, verify the endpoint, credentials, timeout, and
capability configuration. An unavailable optional provider must produce a normalized
error and graceful degradation; it must not silently switch a live run to a different
provider.

## WebSocket reconnect loop

Check API readiness, browser console errors, and the API/worker logs. Confirm the
browser is using the same host and protocol as the API and that the run ID is valid.
Refresh only after capturing the first disconnect timestamp. Reconnect is expected to
restore the read model; it must not duplicate commands or bypass an approval.

## Windows-specific issues

- Use PowerShell commands from [Getting Started](getting-started.md); run shell scripts
  through WSL or Git Bash only when the script is required.
- Docker Desktop must be running with Linux containers enabled.
- A `pnpm` install or build can fail with `EPERM` while creating symlinks. Close IDEs,
  dev servers, and file-indexing tools that hold files open; retry from a writable local
  checkout. Do not replace `pnpm` with npm, npx, or yarn.
- If a port is occupied, identify the owning process before changing `.env` or Compose
  mappings. Keep the chosen mapping consistent across API, web, and browser URLs.
- Long paths and antivirus file locks can make native dependency installation fail.
  Use a short local checkout path and rerun the same frozen install after the lock is
  released.

## Collect a useful diagnostic bundle

Run the smallest relevant checks, then attach:

```powershell
docker compose ps -a
docker compose logs --no-color --tail 300 api worker
uv run alembic current
git rev-parse HEAD
```

Do not attach secrets, tokens, provider credentials, or unredacted model responses.
