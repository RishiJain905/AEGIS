# Getting started

This walkthrough is for a clean machine. It installs the checked-in JavaScript and Python dependencies, applies migrations, starts the local development stack, and shows the production-like local overlay.

## Prerequisites

- Git.
- Node.js `22.x` (the repository pins `22.17.0` in `.node-version`).
- pnpm `11.9.0` or a compatible pnpm `11.x` release. Use pnpm only; do not substitute npm, npx, or yarn.
- uv with Python `3.12` support. The repository requires Python `3.12.x`.
- Docker Desktop with Docker Compose v2 and enough memory for the application, PostgreSQL, Redis, MinIO, and observability containers.
- A POSIX shell for `scripts/bootstrap.sh` (Git Bash, WSL, macOS, or Linux). Windows PowerShell commands are included below where they differ.

Check the tools before installing:

```bash
node --version
pnpm --version
uv --version
docker version
docker compose version
```

## Bootstrap

From the repository root:

```bash
./scripts/bootstrap.sh
```

The script creates `.env` from `.env.example` when needed, runs `pnpm install --frozen-lockfile`, runs `uv sync --frozen --all-packages`, and validates the environment. It does not start Docker or apply migrations.

On Windows PowerShell, use the same commands directly if Git Bash is not available:

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
pnpm install --frozen-lockfile
uv sync --frozen --all-packages
pnpm validate-env
uv run python scripts/validate_env.py
```

## Migrations and development startup

Start the stateful development dependencies and apply the current Alembic head:

```bash
docker compose up -d postgres redis minio
uv run alembic upgrade head
```

The expected migration head for v1.0 is `013_auth_identity`. Start the API and web app in separate terminals:

```bash
uv run uvicorn aegis_api.main:app --app-dir apps/api/src --reload --port 8000
```

```bash
NEXT_PUBLIC_AEGIS_DATA_SOURCE=api pnpm --filter @aegis/web dev
```

In PowerShell, set the web data source before starting the web process:

```powershell
$env:NEXT_PUBLIC_AEGIS_DATA_SOURCE = 'api'
pnpm --filter @aegis/web dev
```

Open `http://localhost:3000`. Development authentication is enabled by `.env`; use the development operator identity in the sign-in page. The API health URLs are `http://localhost:8000/health` and `http://localhost:8000/ready`.

## Production-like local startup

This is the ADR 0033 staging stand-in. It is local only and must not be described as a cloud deployment. Use the fake example values only on the local machine:

```bash
cp .env.production.example .env.production
export AEGIS_PROD_ENV_FILE=.env.production
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml build api web worker simulator
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
uv run python scripts/deploy_smoke_test.py --environment local --env-file .env.production
```

The overlay uses loopback ports `18000` (API), `13000` (web), `55432` (PostgreSQL), and `56379` (Redis), and runs the one-shot `migrate` service before application services. Stop it with:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml down
```

On PowerShell, use `$env:AEGIS_PROD_ENV_FILE = '.env.production'` instead of `export`. For a full local release gate, run `scripts/run_release_validation.ps1 -Environment local` on Windows or `scripts/run_release_validation.sh --environment local` on POSIX.

## Deterministic demo

With the development stack or production-like API running:

```bash
uv run python scripts/demo_v1.py --headless --seed 42
```

The script logs in as the seeded local operator, creates `scenarios/operation-silent-relay` with seed `42`, verifies the API and persisted graph endpoint, then prints the next UI and observability paths. See [release/demo-manifest.json](../release/demo-manifest.json) for the expected headline outcomes.
