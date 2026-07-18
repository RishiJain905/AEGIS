# Migration runbook

PostgreSQL is authoritative. Alembic migrations run as a single controlled job,
never independently from each application replica.

## Safety checks

Before a hosted migration job is approved:

- confirm the target image digest and expected Alembic head;
- take and verify a PostgreSQL backup, recording the backup identifier;
- check active sessions, long-running transactions, lock waits, and available
  storage;
- review the migration for expand/contract compatibility, indexes, locks,
  table rewrites, and data-loss behavior;
- confirm the application can run against both the old and new schema during a
  rolling deployment; and
- define the forward-fix and restore decision before starting.

## Ordering

For a compatible change, use:

1. deploy the migration job and run `alembic upgrade head` once;
2. verify `alembic_version` and migration-specific invariants;
3. deploy the application image that consumes the new additive schema;
4. backfill in a bounded, observable job if needed; and
5. remove old columns or constraints only in a later reviewed migration after
   all old readers are gone.

Do not run migrations from API startup or from every worker replica. A failed
migration blocks the application rollout and leaves the previous compatible
image in place.

## Local rehearsal command

With the production-shaped stack configured, the overlay expresses the same
job boundary:

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
  'select version_num from alembic_version;'
```

The Compose `api`, `worker`, and `simulator` services depend on the migration
job completing successfully. The expected current head is
`013_auth_identity`.

## Rollback

Prefer a forward fix. A migration is eligible for `alembic downgrade` only when
its author has explicitly reviewed reversibility, data preservation, lock
behavior, and the application version that will read the reverted schema. A
restore is the recovery path for destructive or partially applied changes; it
is not an automatic deployment step.
