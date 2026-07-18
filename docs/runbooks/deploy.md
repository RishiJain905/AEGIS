# Future deployment runbook

Status: documentation-only. Phase 33 does not provision infrastructure, use a
domain, contact a registry, or execute a deployment. The local production-like
Compose stack is the only deployment-shaped environment currently authorized.

## Manual review gates

An owner-approved activation task must record all of these before any provider
API is contacted:

1. Scope, provider, account, region, budget ceiling, and cost alerts are
   approved in writing.
2. The selected provider adapter preserves the module inputs in
   `infra/terraform/modules/deployment_shape` and has an encrypted, locked
   remote state configuration outside this repository.
3. Image digests, source revision, SBOMs, vulnerability results, and license
   review are attached to the release record.
4. Secret-manager names are mapped for every required variable. No value is
   pasted into Terraform, a workflow, a ticket, or a shell history.
5. Private network routes, data-service ingress, restricted worker egress,
   HTTPS certificate, CORS origins, and HSTS behavior are reviewed.
6. The migration plan, backup age, restore evidence, rollback image, and
   operator/on-call ownership are reviewed.

Each gate is a stop-the-line gate. A failed gate returns the release to review;
it is not bypassed with a manual command.

## Future activation sequence

The following is the order for a separately approved provider activation. It is
not an instruction to run against the current repository:

1. Validate the chosen provider module offline, then run a no-apply plan with
   the intended variables. Review the plan for only the approved runtime,
   private PostgreSQL/Redis/object storage, secret references, edge TLS,
   telemetry, and backups.
2. Apply networking and secret-manager references after the cost and security
   gates pass. Confirm data services have no public ingress.
3. Publish immutable images through the separately approved artifact process;
   record the digest and provenance in the release record.
4. Run the migration job once, using the image’s `alembic upgrade head`
   command. Capture the migration head and database backup identifier.
5. Start the runtime with the migration job as a dependency. Wait for liveness,
   readiness, and worker health. Keep the first rollout at the approved canary
   capacity.
6. Run the smoke checks against the approved HTTPS staging URL, including the
   unauthenticated 401 and authenticated WebSocket/session paths. Do not treat
   a successful TCP connection as authorization evidence.
7. Review logs, metrics, traces, dependency probes, queue depth, and error rate
   during the observation window. Promote only after the named reviewer signs
   off.
8. Record the exact image digests, migration head, backup, probe results, and
   reviewer identities in the release record.

The current CI intentionally stops before steps 2–8. It has no registry login,
push, cloud credential, deploy job, DNS operation, or approval environment.

## Local stand-in

Use `.env.production.example` (or a local ignored copy), then:

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
uv run python scripts/deploy_smoke_test.py --environment local \
  --env-file .env.production
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml down
```

This is the maximum deployment-like action performed by Phase 33.
