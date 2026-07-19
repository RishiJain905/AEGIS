# Phase 33 Handoff — Deployment Readiness Without Executed Deployment

## Status

`READY FOR VALIDATION`

This checkout implements deployment readiness only. No cloud resource, domain, DNS
record, hosted data service, registry push, credential, or deployment was created or
executed. All local production-like resources were torn down after validation.

## Implemented

- **Production-like local stack:** `docker-compose.prod.yml` overlays the existing
  Compose stack with production environment mode, external env-file references,
  restart policies, resource limits, healthchecks, loopback-only host ports, a
  one-shot Alembic migration job, and Phase 32 hardening (`read_only`, `tmpfs`,
  `cap_drop: ALL`, and `no-new-privileges`). The full stack reached healthy state
  locally and passed the vertical smoke test.
- **Cloud-neutral target shape:** `infra/terraform/` describes dev, staging, and
  production container runtime, managed PostgreSQL/Redis/object storage, secret
  references, private data networking, edge TLS, telemetry, and backups through a
  small provider-neutral module. It intentionally uses Terraform built-ins only;
  provider substitution and remote state are documented for a separately approved
  activation task.
- **Deployment contract:** `docs/deployment.md` defines service environment
  variables, Phase 32 security variables, image/provenance requirements, probes,
  capacity guidance, private networking, HTTPS, and secret ownership.
- **Runbooks and rehearsals:** deployment, migration, rollback, and backup/restore
  runbooks are under `docs/runbooks/`. Local rollback and PostgreSQL dump/restore
  transcripts are recorded under `docs/runbooks/evidence/`.
- **CI readiness:** `.github/workflows/deploy-readiness.yml` builds production
  images, validates Compose and Terraform, runs the local smoke path, and uploads
  image metadata/SBOM artifacts. Actions are SHA-pinned. There are no login, push,
  publish, migration-deploy, or active deployment steps.
- **Smoke command:** `scripts/deploy_smoke_test.py` checks health/readiness,
  unauthenticated authorization (`401`), WebSocket upgrade reachability, and the
  Alembic migration head. `--environment staging` refuses unless
  `AEGIS_STAGING_URL` is explicitly configured.

The implementation satisfies the revised Phase 33 deployment-readiness outcome,
while the original managed-cloud activation work remains deliberately deferred by
ADR 0033.

## Files added

- `.env.production.example` — clearly fake, valid-shaped production-mode local
  configuration; no real credentials.
- `.github/workflows/deploy-readiness.yml` — deploy-free build/config/validation
  workflow with pinned actions.
- `docker-compose.prod.yml` — production-shaped local overlay.
- `docs/deployment.md` — deployment environment, artifact, probe, capacity, and
  network contracts.
- `docs/handoffs/33-cloud-deployment-HANDOFF.md` — this handoff.
- `docs/runbooks/deploy.md`
- `docs/runbooks/migration.md`
- `docs/runbooks/rollback.md`
- `docs/runbooks/backup-restore.md`
- `docs/runbooks/evidence/phase-33-rollback-transcript.txt`
- `docs/runbooks/evidence/phase-33-backup-restore-transcript.txt`
- `infra/terraform/README.md`
- `infra/terraform/modules/deployment_shape/{variables,main,outputs}.tf`
- `infra/terraform/environments/{dev,staging,production}/{main,outputs}.tf`
- `scripts/__init__.py`
- `scripts/deploy_smoke_test.py`
- `tests/deployment/test_deploy_smoke_test.py`
- `tests/deployment/test_simulator_service.py`

The owner-provided governing revision
`docs/AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md`
was preserved in the working tree and used as the controlling scope.

## Files modified

- `.gitignore` — ignores the local production env file and Terraform working
  directories.
- `apps/api/Dockerfile` — copies `alembic.ini` and `migrations` into the runtime
  image.
- `apps/api/pyproject.toml`, `uv.lock` — add Alembic to the API runtime contract.
- `apps/web/Dockerfile` — accepts production Compose build-time API/WebSocket URLs.
- `docker-compose.yml` — removes the baked development WebSocket token default.
- `infra/README.md` — links the Terraform deployment-shape documentation.
- `pyproject.toml` — makes the repository package importable by the smoke-test
  unit tests without changing application package boundaries.
- `scripts/verify.ps1` — adds the `-Deployment` validation gate and guaranteed
  command evidence for Compose, images, Terraform, smoke, and teardown.
- `services/simulation/src/aegis_simulation/runner.py` — adds a signal-aware,
  graceful managed `service` command required by the production-shaped simulator
  container.
- `docs/handoffs/32-security-hardening-HANDOFF.md` — Prettier-only Markdown
  emphasis normalization required by the existing repository format gate; no
  security or behavior change.

## Files removed

None.

## Contracts introduced or changed

- **Deployment environment contract:** documented in `docs/deployment.md`; the
  service settings remain owned by their existing phases. Phase 32 variables are
  explicitly included: request body limit, request rate/burst/bucket limits, HSTS
  enablement/max age, and provider egress allowlist.
- **Probe contract:** API `/health` is liveness and `/ready` is dependency-aware
  readiness; WebSocket `/ws/v1/realtime` must complete an upgrade attempt. The
  smoke command treats an unauthenticated protected API endpoint returning `401`
  as the authorization boundary check.
- **Artifact contract:** production images use immutable release tags plus digests
  and must have provenance/SBOM metadata; `latest` and registry publication are
  prohibited by the local contract.
- **Terraform shape contract:** the module exposes typed variables for runtime,
  data services, secrets, network, edge TLS, telemetry, and backups. It creates no
  provider resources and stores no state.
- **Simulator service contract:** `aegis-simulator service` is a managed process
  that exits cleanly on SIGTERM/SIGINT; the injected-event unit test proves its
  shutdown behavior.

No durable event, API schema, domain identifier, authorization policy, or migration
version was changed. The existing migration head remains `013_auth_identity`.

## Database migrations

No new migration was added. The production-shaped `migrate` service runs
`alembic upgrade head` before API/worker/simulator readiness. The API runtime image
now carries the existing Alembic configuration and migration tree. Local restore
rehearsal verified migration head `013_auth_identity` in a restored database.

## Environment and configuration changes

- Use `.env.production.example` as the local template only; copy it to the ignored
  `.env.production` if a local operator wants the canonical filename.
- The Compose overlay requires `--env-file .env.production` (or an explicitly
  documented fake example) and uses `${...}` references for secrets; secret values
  are not baked into images or Compose YAML.
- `AEGIS_PROD_ENV_FILE` selects the overlay env-file path for interpolation.
- `AEGIS_SMOKE_POSTGRES_PORT`, `AEGIS_API_HOST_PORT`, and
  `AEGIS_WEB_HOST_PORT` make the local production-shaped endpoints coexist with a
  separately running development container.
- The smoke command supports `--environment local|staging`, `--env-file`,
  `--base-url`, `--postgres-url`, and `--expected-migration-head`.

## Generated artifacts and fixtures

- `uv.lock` was regenerated after adding Alembic.
- CI and the local readiness workflow generate image-inspect metadata and
  CycloneDX SBOM files as temporary artifacts; nothing is published externally.
- Local Terraform `.terraform/` directories are ignored and no state files are
  retained.
- Rehearsal transcripts are plain-text evidence, not production backups.

## Tests added

- `tests/deployment/test_deploy_smoke_test.py` uses a fake transport to prove the
  health, readiness, `401`, WebSocket, and migration-head checks; it also covers a
  failed authorization response, missing staging configuration, and local env-file
  URL resolution.
- `tests/deployment/test_simulator_service.py` injects a stop event and proves the
  managed simulator service exits on shutdown.

Focused deployment tests and the full repository test gate passed. No tests were
deleted, skipped, or weakened.

## Commands executed and results

The following commands were executed in this checkout. The Terraform CLI is not
installed on the host, so the pinned Terraform image was used with
`-backend=false`; this is offline validation and uses only built-in Terraform
constructs.

| Command                                                                                                                                                                 | Result                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `uv run pytest tests/deployment -q`                                                                                                                                     | `5 passed` (after the final implementation)                                                                   |
| `uv run mypy scripts/deploy_smoke_test.py tests/deployment`                                                                                                             | `Success: no issues found in 3 source files`                                                                  |
| `uv run ruff check scripts tests/deployment`                                                                                                                            | `All checks passed`                                                                                           |
| `docker compose -f docker-compose.yml config --quiet`                                                                                                                   | exit `0`                                                                                                      |
| `$env:AEGIS_PROD_ENV_FILE='.env.production.example'; docker compose --env-file .env.production.example -f docker-compose.yml -f docker-compose.prod.yml config --quiet` | exit `0`                                                                                                      |
| `docker run --rm ... terraform:1.9.8@sha256:18f998... fmt -check -recursive`                                                                                            | exit `0`                                                                                                      |
| Terraform `init -backend=false -input=false` + `validate` for `dev`, `staging`, `production`                                                                            | each printed `Success! The configuration is valid.`                                                           |
| `docker compose ... up -d --wait` with the production overlay                                                                                                           | all services healthy; migration job exited `0`                                                                |
| `uv run python scripts/deploy_smoke_test.py --environment local --env-file .env.production.example`                                                                     | `PASS health`, `PASS ready`, `PASS unauthenticated`, `PASS websocket`, `PASS migration`, `DEPLOY SMOKE: PASS` |
| `uv run python scripts/deploy_smoke_test.py --environment staging`                                                                                                      | refused with `REFUSED: staging smoke is disabled until AEGIS_STAGING_URL is configured` (exit `2`)            |
| `& .\scripts\verify.ps1 -Deployment`                                                                                                                                    | all baseline and deployment stages `ok`; final line `VERIFY: PASS`; exit `0`                                  |
| final production-like teardown: `docker compose ... down --volumes --remove-orphans`                                                                                    | named Phase 33 containers, volumes, and network removed                                                       |

The deployment-aware verifier’s final tail was:

```text
--- [compose-prod-up] ok
--- [deploy-smoke] ok
--- [compose-prod-down] ok
VERIFY: PASS
PASS health
PASS ready
PASS unauthenticated
PASS websocket
PASS migration
DEPLOY SMOKE: PASS
VERIFY_EXIT=0
```

The verifier also passed `format`, `eslint`, `tsc`, `vitest`, `ruff`, `mypy`,
`import-linter`, `pytest --ignore=tests/integration`, and `contracts`.

The exact Terraform image invocations used by the verifier were:

```text
docker run --rm -v F:\Personal\A.E.G.I.S\AEGIS\infra\terraform:/workspace -w /workspace hashicorp/terraform:1.9.8@sha256:18f9986038bbaf02cf49db9c09261c778161c51dcc7fb7e355ae8938459428cd fmt -check -recursive
docker run --rm --entrypoint /bin/sh -v F:\Personal\A.E.G.I.S\AEGIS\infra\terraform:/workspace -w /workspace hashicorp/terraform:1.9.8@sha256:18f9986038bbaf02cf49db9c09261c778161c51dcc7fb7e355ae8938459428cd -c "terraform -chdir=environments/dev init -backend=false -input=false && terraform -chdir=environments/dev validate"
docker run --rm --entrypoint /bin/sh -v F:\Personal\A.E.G.I.S\AEGIS\infra\terraform:/workspace -w /workspace hashicorp/terraform:1.9.8@sha256:18f9986038bbaf02cf49db9c09261c778161c51dcc7fb7e355ae8938459428cd -c "terraform -chdir=environments/staging init -backend=false -input=false && terraform -chdir=environments/staging validate"
docker run --rm --entrypoint /bin/sh -v F:\Personal\A.E.G.I.S\AEGIS\infra\terraform:/workspace -w /workspace hashicorp/terraform:1.9.8@sha256:18f9986038bbaf02cf49db9c09261c778161c51dcc7fb7e355ae8938459428cd -c "terraform -chdir=environments/production init -backend=false -input=false && terraform -chdir=environments/production validate"
```

Each command exited `0`; the three environment commands printed
`Success! The configuration is valid.`

## Rehearsal evidence

- **Rollback:** `docs/runbooks/evidence/phase-33-rollback-transcript.txt` records
  a local app-level rollback by retagging the already-built images with
  `phase33-rollback-known-good`, recreating the production-shaped stack, confirming
  all app containers healthy, and rerunning the full smoke checks. No schema
  rollback was attempted; the runbook requires a forward migration fix unless a
  separately approved reversible migration exists.
- **Backup/restore:**
  `docs/runbooks/evidence/phase-33-backup-restore-transcript.txt` records
  `pg_dump --format=custom` inside the Compose PostgreSQL container, creation of an
  isolated restore database, `pg_restore --exit-on-error --no-owner`, verification
  of `013_auth_identity`, and cleanup. The recorded dump was `118.3K`. Object
  storage synchronization expectations are documented but were not simulated by a
  provider-free local command.

## Architecture decisions and ADRs

- Governing revision: `docs/AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md`.
- The revision explicitly authorizes readiness artifacts and local rehearsal while
  prohibiting executed deployment, credentials, and cost-incurring resources. The
  provider-neutral Terraform inventory and local-only Compose overlay follow that
  boundary.
- No new architecture technology or provider SDK was introduced. No existing
  package dependency or domain contract was duplicated.

## Known limitations

- Terraform is intentionally provider-neutral and does not create cloud resources;
  provider-specific resource modules, remote-state storage, DNS, and certificate
  issuance require a future owner-approved activation task.
- The local Compose stack uses MinIO and loopback ports as stand-ins for object
  storage and an HTTPS edge. It validates shape and probes, not cloud IAM or TLS
  issuance.
- The CI workflow is configured to run the local Docker smoke path. The local
  `scripts/verify.ps1 -Deployment` gate is the executed evidence in this
  checkout; hosted-runner execution remains subject to the repository’s CI
  runtime and Docker availability.
- The WebSocket smoke validates a reachable upgrade response. It does not create a
  real authenticated session because the requested check is explicitly the
  unauthenticated `401` boundary.

## Deferred work

- Cloud-provider selection and resource creation.
- Remote Terraform backend/state, managed service provisioning, DNS, certificates,
  registry publication, deployment approvals, and secret-manager binding.
- Real staging rollback/restore rehearsal; local stand-ins are the only permitted
  rehearsal under ADR 0033.
- Object-storage sync/restore rehearsal against a hosted provider.

## Risks for dependent phases

- Any future deployment manifest must retain the Phase 32 hardening settings and
  provider egress allowlist.
- A deployment activator must replace fake `.invalid.example` OIDC values and all
  local passwords/keys through an approved secret manager path; never copy the
  example values into a real environment.
- The migration job must remain a separate, observable rollout step. Application
  rollback and schema rollback are not interchangeable.
- Port overrides and Compose `!override` tags are intentionally local-overlay
  behavior; a future provider module must express the equivalent private ingress
  and edge routing explicitly.

## Acceptance criteria evidence

1. **Staging is reproducible from IaC and runs the complete vertical slice.** The
   dev/staging/production Terraform environments each pass offline init/validate
   and expose the same typed deployment-shape module. Staging execution is not
   performed because ADR 0033 prohibits real deployment; the local production-shaped
   stack is the executed vertical-slice evidence.
2. **PostgreSQL/Redis are private and secrets are external.** The overlay binds
   data ports to loopback for local coexistence; the Terraform contract describes
   private data networking; Compose secrets come from env-file references and the
   example contains only fake values.
3. **Migrations are controlled and rollback is rehearsed.** The `migrate` service
   gates application dependencies, the migration runbook defines ordering and
   safety checks, the rollback transcript proves app-image rollback, and the
   backup/restore transcript proves a local PostgreSQL restore.
4. **Another agent/operator can reproduce deployment from docs.** The deployment
   contract, four runbooks, Terraform README, `.env.production.example`, exact
   Compose commands, smoke command, and `scripts/verify.ps1 -Deployment` provide
   the reproducible local path and explicit future activation gates.

## Prohibited-shortcut confirmation

No cloud resources, domains/DNS, hosted PostgreSQL/Redis/object storage, registry
pushes, real credentials, deployment execution, or cost-incurring operation was
used. No workflow contains an active deploy/publish/push/login step. No tests were
deleted, skipped, loosened, or rewritten to make the phase pass; no production path
uses a mock as its service implementation; and all reported validation commands
were run against the current uncommitted tree.
