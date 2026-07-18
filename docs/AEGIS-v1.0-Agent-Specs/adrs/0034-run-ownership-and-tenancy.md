# ADR 0034: Run Ownership and Tenancy

## Status

Accepted (v1.0 release hardening — resolves AEGIS-OITB-008 and AEGIS-BUG-010)

## Context

Runs had no owner. `create_run` never recorded who started a run; `GET /api/v1/runs`
returned `list_all()` to any authenticated identity; and `GET /api/v1/runs/{id}` (plus
the lifecycle commands) authorized only the coarse `runs:read` / `runs:write` permission
with no per-resource check. Consequences (final review AEGIS-OITB-008):

- Any authenticated viewer/analyst could list and open runs they did not create.
- On login a non-admin landed in a pre-existing/seeded active run, so the scenarios page
  looked already-started or broken (AEGIS-BUG-010): its per-row action resolved to an
  existing/hardcoded run id (`DEFAULT_SYNTHETIC_RUN_ID`) rather than starting a run.

ADR 0031 already models identity (`AuthenticatedActorV1`), a deny-by-default permission
matrix, and an unused per-resource `ResourceAccessGrantV1` mechanism. This ADR adds the
missing ownership dimension without introducing a new grant workflow.

## Decision

1. **Runs are owned by the creating actor.** A run records `ownerUserId` = the
   authenticated actor's `userId` at creation time. `create_run` stamps it from the
   session actor (never from a client-supplied field).
2. **Single-tenant-per-user model.** There are no teams/orgs in v1.0; a run belongs to
   exactly one owner. Sharing, if ever needed, is layered later via the existing
   `ResourceAccessGrantV1` mechanism — out of scope here.
3. **Listing is scoped to the caller.** `GET /api/v1/runs` returns only the caller's own
   runs via a new `PostgresRunRepository.list_for_owner`. An admin (holding `admin:manage`)
   sees all runs via `list_all`.
4. **Opening / commanding a run requires owner-or-admin.** `GET /api/v1/runs/{id}`, the
   run-scoped read routes (`/graph`, `/bootstrap`, `/incidents`, `/alerts`), and the
   lifecycle commands (`pause`/`resume`/`stop`/`step`) authorize owner-or-admin on top of
   the existing `runs:read` / `runs:write` permission. Non-owner, non-admin ⇒ 403;
   absent run ⇒ 404. Legacy rows with a null owner are treated as admin-only (fail-closed).
5. **Additive optional contract field, schemaVersion unchanged.** `ownerUserId`
   (`AuthoredId`, `user:` namespace) is added to `RunV1` in both `contracts-python` and
   `contracts-ts` as an optional/nullable field. Per `docs/contracts/versioning.md`
   ("Add optional field, same semantics ⇒ same schemaVersion"), `RUN_SCHEMA_VERSION`
   stays `1`; only golden fixtures, generated schemas, and the compatibility manifest are
   updated. This keeps old persisted payloads and wire consumers valid.
6. **Nullable column + demo/admin backfill.** Migration `014_run_ownership` adds a nullable
   `owner_user_id` column (indexed for `list_for_owner`) and backfills pre-ownership rows
   — the seeded Silent Relay / synthetic runs — to the demo/admin owner `user:admin-alpha`
   (both the column and the JSONB payload, so the domain object agrees). The column is
   deliberately **not** a foreign key to `auth_users`: auth users are seeded at app startup,
   not by migration, so an owner id may not exist at migrate time (mirrors
   `security_audit_events.actor_user_id`).
7. **Scenarios page reflects ownership.** The page offers a primary "Start new run"
   (real create-run mutation with the scenario package + seed, then navigate to the new
   run) and a secondary "Resume latest run" shown **only** when the current account owns a
   most-recent run for that scenario. The hardcoded `DEFAULT_SYNTHETIC_RUN_ID` fallback and
   the arbitrary-run resolver are removed. Runs owned by the demo/admin identity are
   labelled as demo data.

## Consequences

- A viewer/analyst can no longer enumerate or open other users' runs; a fresh account with
  no runs sees "Start new run" rather than a stranger's in-progress run.
- `GET /api/v1/runs` semantics change from global to caller-scoped (admins retain the
  global view). Any tooling that assumed a global list must authenticate as an admin.
- Ownership is immutable in v1.0 (set once at creation, never transferred). Transfer or
  sharing would reuse `ResourceAccessGrantV1` and is not implemented here.
- Seeded demo runs are owned by `user:admin-alpha`; only an admin sees them in the list,
  which is the intended tenancy, not a regression.
- No new platform technology, event shape, or breaking contract change is introduced.

## Alternatives considered

- **Bump `RUN_SCHEMA_VERSION` to 2 and make `ownerUserId` required.** Rejected: it would
  break every existing persisted run payload and force a data migration of the JSONB
  identity for no compatibility benefit, when an additive optional field satisfies the
  versioning policy.
- **Reuse `ResourceAccessGrantV1` as the sole ownership model (no column).** Rejected for
  v1.0: grants are a sharing/ACL mechanism; encoding basic single-owner tenancy as a grant
  per run adds a write on every create and a join on every list without a product need yet.
- **Return 404 for non-owned existing runs (hide existence).** Rejected: the review's
  acceptance criteria specify 403 for an existing run the caller does not own; 404 is
  reserved for genuinely absent runs.
