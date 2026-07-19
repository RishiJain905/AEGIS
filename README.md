# AEGIS Command v1.0.0

AEGIS is a local-first platform for synthetic defensive cyber operations, deterministic simulation, detection/ML evaluation, human-approved agent proposals, replay, and after-action review. It does not execute real intrusion, exploit, or production-remediation activity.

## Quick start

Requirements and clean-machine instructions are in [docs/getting-started.md](docs/getting-started.md). The shortest supported setup is:

```bash
./scripts/bootstrap.sh
docker compose up -d --build --wait
uv run alembic upgrade head
```

Open `http://localhost:3000` for the web command centre. The API is at `http://localhost:8000`; health and readiness are `/health` and `/ready`.

To run the deterministic release demo against the local stack:

```bash
uv run python scripts/demo_v1.py --headless
```

The documented demo seed is `42`. It creates an Operation Silent Relay run and prints the URLs and operator steps for graph, detection/ML, mock-provider agents, approval, replay, cinematic mode, and after-action review.

## Production-like local validation

ADR 0033 defines the local production-like Compose overlay as the only staging stand-in for v1.0. It does not provision cloud resources, use cloud credentials, push images, or deploy. Follow [docs/deployment.md](docs/deployment.md) and [docs/runbooks/deploy.md](docs/runbooks/deploy.md) for the overlay.

```powershell
.\scripts\run_release_validation.ps1 -Environment local
```

The release gate writes schema-versioned evidence under [docs/release/evidence](docs/release/evidence). The offline repository gate is:

```powershell
.\scripts\verify.ps1
```

## Documentation

- [Getting started](docs/getting-started.md) — prerequisites, bootstrap, migrations, development, and production-like local startup.
- [Operator guide](docs/operator-guide.md) — scenarios, approvals, replay, scoring, and observability.
- [Troubleshooting](docs/troubleshooting.md) — Docker, migrations, providers, WebSocket reconnects, and Windows issues.
- [Scenario authoring](docs/scenario-authoring.md) and [provider setup](docs/agents/model-providers.md).
- [Release notes](docs/release/v1.0.md), [checklist](docs/release/checklist.md), and [known issues](docs/release/known-issues.md).
- [Security scope and reporting](docs/security/scope.md).

The binding architecture contract is [architecture.md](architecture.md). Shared contract ownership and schema compatibility are defined in [docs/contracts/versioning.md](docs/contracts/versioning.md).
