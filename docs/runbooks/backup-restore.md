# Backup and restore runbook

PostgreSQL backups cover authoritative state, event history, approvals, audit,
and migration metadata. Object storage is a separate artifact plane and must be
backed up or replicated with checksums and version identifiers.

## PostgreSQL hosted pattern

1. Record the database engine/version, backup timestamp, retention policy,
   encryption key reference, and migration head.
2. Take a consistent custom-format dump or provider snapshot. Keep credentials
   in the provider secret manager and pass only references to the job.
3. Verify the dump can be listed and its checksum matches the backup record.
4. Restore to an isolated database or instance with the same or a compatible
   PostgreSQL major version.
5. Run `alembic current`, schema invariants, row-count sanity checks, and a
   read-only application smoke test against the isolated restore.
6. Cut over only after the incident owner and data owner approve; preserve the
   original database for the retention window.

Representative commands (adapt flags to the approved provider):

```bash
pg_dump --format=custom --no-owner --file=aegis.dump "$POSTGRES_URL"
pg_restore --exit-on-error --no-owner --dbname="$RESTORE_POSTGRES_URL" aegis.dump
psql "$RESTORE_POSTGRES_URL" -Atc \
  'select version_num from alembic_version;'
```

## Object-storage expectations

Keep artifact metadata in PostgreSQL: object key, checksum, content type, size,
schema/model version, and creation time. The provider backup job must preserve
private ACLs, object versioning, retention/legal-hold policy, and encryption key
references. A future provider-specific runbook should use an equivalent
server-side sync or versioned replication command (for example `aws s3 sync` or
`mc mirror`) without exposing credentials or making the bucket public. Restore
the exact referenced version and verify its checksum before reattaching it to a
report, model, snapshot, or replay.

## Local rehearsal

The local Compose PostgreSQL is the rehearsal target. It uses a custom-format
dump held inside the container and restores into a separate temporary database,
so the authoritative rehearsal database is not dropped:

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file=/tmp/aegis-phase33.dump'
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  createdb -U "$POSTGRES_USER" aegis_restore_rehearsal
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" \
  --dbname=aegis_restore_rehearsal /tmp/aegis-phase33.dump'
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d aegis_restore_rehearsal -Atc \
  'select version_num from alembic_version;'
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  dropdb -U "$POSTGRES_USER" aegis_restore_rehearsal
```

The executed transcript is recorded in
`docs/runbooks/evidence/phase-33-backup-restore-transcript.txt`.
