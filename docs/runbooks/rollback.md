# Rollback runbook

Rollback is a reviewed release action, not an automatic workflow. Phase 33
rehearses the application/image path against the local production-shaped
Compose stack; no cloud rollback is executed.

## Image rollback

1. Stop promotion and capture the failing image digest, migration head,
   request/error metrics, and trace identifiers.
2. Select the last known-good immutable image digest and verify its SBOM and
   compatibility with the current database head.
3. Repoint API, web, worker, and simulator to that digest as one release unit.
   Do not roll back only the API while leaving incompatible workers running.
4. Restart the runtime, wait for liveness/readiness, then run the smoke test.
5. Observe the error rate and queue/outbox lag for the agreed rollback window.
6. Open a follow-up incident for the failed release; do not retry promotion
   until the reviewer signs off.

The local overlay accepts `AEGIS_API_IMAGE`, `AEGIS_WEB_IMAGE`,
`AEGIS_WORKER_IMAGE`, and `AEGIS_SIMULATOR_IMAGE` overrides. The rehearsal uses
the same known-good local image under a second tag to validate that mechanism.

## Migration rollback strategy

- Prefer a forward-compatible application rollback with the new schema left in
  place.
- Use `alembic downgrade` only for an explicitly reversible migration after a
  backup and owner review.
- For destructive or ambiguous changes, restore PostgreSQL to a new isolated
  instance, validate invariants, then perform a controlled cutover; do not
  overwrite the authoritative database from an unverified dump.
- Object-storage artifacts are immutable/versioned. Restore the referenced
  object version and verify its checksum before making it visible.

## Local rehearsal

The exact command transcript is recorded in
`docs/runbooks/evidence/phase-33-rollback-transcript.txt`. It starts the local
production-shaped stack, confirms the baseline, switches each application
image reference to the known-good rollback tag, waits for health, reruns the
smoke checks, and tears the stack down. The migration head remains unchanged;
this is intentionally an application-level rollback rehearsal.
