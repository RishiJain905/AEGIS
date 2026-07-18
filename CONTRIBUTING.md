# Contributing to AEGIS

Keep changes small, explicit, and testable. AEGIS is simulation-only; contributions
must preserve the safety boundaries in [Security Scope](docs/security/scope.md).

## Local setup

Follow [Getting Started](docs/getting-started.md). Use Node 22, pnpm, uv, and Docker
Compose as documented. Do not substitute npm, npx, or yarn.

## Before opening a change

Run the narrowest relevant tests while iterating, then run the repository gate:

```powershell
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
uv run ruff check .
uv run mypy
uv run pytest -q
.\scripts\verify.ps1
```

For release-facing changes also run `.\scripts\run_release_validation.ps1 -Environment local`.
Do not claim a check passed without retaining its command and result.

## Contracts and scenarios

Update the relevant contract, schema, fixture, and documentation together. Scenario
packages are declarative and versioned; validate and checksum them with the Scenario
SDK. Never rewrite an already published scenario version in place.

## Pull requests

Describe the behavior change, affected contracts, migration impact, verification
commands, and known limitations. Include evidence links for release or security work.
Keep generated artifacts reproducible and do not include credentials, local databases,
or unredacted model output.

## Security reports

Use the private reporting process in [Security Scope](docs/security/scope.md), not a
public issue, for suspected vulnerabilities.
