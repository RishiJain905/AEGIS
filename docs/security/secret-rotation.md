# Secret Management and Rotation

AEGIS reads secrets through `SecretProvider`; `EnvironmentSecretProvider` is the default adapter over process environment with parsed settings fallback. A managed secret store can replace that adapter without changing startup validation. Production startup fails before database or worker I/O when required configuration is missing or uses known development placeholders.

## Production values

Required at API startup:

- `POSTGRES_PASSWORD`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `AEGIS_OIDC_ISSUER`
- `AEGIS_OIDC_CLIENT_ID`
- `AEGIS_OIDC_CLIENT_SECRET`

Production validation also rejects the `.env.example` localhost values for PostgreSQL, Redis, object storage, the OIDC callback, CORS origins, and the web base URL. This prevents a production process from silently starting against development endpoints.

When a network provider is enabled, its API credential must also be supplied through the deployment secret source. Provider destinations are independently constrained by `AEGIS_PROVIDER_EGRESS_ALLOWLIST`.

## Rotation procedure

1. Create a new credential with the minimum required permissions. Do not modify `.env.example` with real values.
2. Stage the new value in the deployment secret source and roll processes so startup validation exercises it.
3. Verify `/live`, `/ready`, authentication, object-storage access, and one deterministic provider fake or approved provider probe. Inspect logs only for secret names/error codes; values must remain redacted.
4. Revoke the old credential after all processes use the new value. For providers that cannot overlap credentials, use a bounded maintenance window and rollback value held in the secret manager.
5. Record actor, secret name, rotation time, validation result, and revocation confirmation in the operational audit system. Never record the value.

## Service-specific notes

- PostgreSQL: create/rotate the role password, update the secret source, roll API/workers, confirm readiness, then invalidate the old password.
- Object storage: issue a second access key, restrict it to the AEGIS bucket, roll and validate signed/private object operations, then revoke the old key.
- OIDC: add the new client secret at the identity provider, deploy it, validate login/callback/logout, then remove the old secret.
- Model providers: create a scoped key with spend limits, deploy and validate through the allowlisted base URL, then revoke the old key.

Emergency rotation follows the same order but may revoke first when active compromise outweighs temporary unavailability. After any suspected leak, invalidate sessions/tokens as applicable and review redacted security/audit events for misuse.
