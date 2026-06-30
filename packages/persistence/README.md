# AEGIS Persistence

PostgreSQL persistence for AEGIS v1.0: SQLAlchemy 2 async access, Alembic migrations, repository protocols, and transactional outbox.

## Ownership

- ORM table definitions and mappers
- Repository protocols and PostgreSQL adapters
- `PostgresUnitOfWork` for atomic state + event + outbox commits
- Deterministic local seed infrastructure

## Dependencies

- `aegis-contracts` for domain types (never duplicate shapes)
- Must not import `aegis_api` or service entry points

## Consumers

- `apps/api` — session wiring and health checks
- `services/*` — domain persistence (later phases)
