# Known release issues

These are explicit records, not silent waivers. They remain subject to the blocker and
exception policies.

| Issue | Severity/status | Evidence and disposition |
| --- | --- | --- |
| Web image has 23 HIGH transitive findings | B2 / open triage | The Phase 32 scan-triage record identifies the affected transitive packages. Fix or create a finding-specific approved exception with digest, controls, owner, and expiry; do not suppress the scan. |
| 3D first render is currently approximately 4–8 seconds | B2 baseline / measured each release | `graph.3d.mount_to_visible` records the real first-frame latency and capability fallback. A hard p99 over budget becomes B1; the latency is not hidden behind a generic readiness check. |
| Windows `pnpm build` can fail with symlink `EPERM` | B2 environment issue / open | Retain the exact build output in deployment evidence and use the documented local mitigation/runner environment. A reproducible release build failure remains B1 until fixed. |
| Production hosted OIDC login is not implemented (deployment-readiness only) | B2 known limitation / documented | AEGIS v1.0 is deployment-readiness only (ADR 0033) with no real IdP to test against. `ConfiguredOidcProvider.exchange_code` deliberately fails closed with a descriptive error rather than shipping an unverified authorization-code token exchange; the production authorization-code flow (token/JWKS exchange, ID-token signature/nonce/PKCE validation, subject provisioning) is not yet complete. Supported v1.0 auth paths are the local/dev identities and the documented modes. Enabling hosted auth requires completing the OIDC token-exchange adapter first. |
| OIDC login state is stored in-process (single-instance only) | B2 known limitation / documented | Pending OIDC login state (`_OIDC_STATE` in `apps/api/.../auth/router.py`) is process-local with a TTL sweep and capacity cap. A callback must reach the same API instance that served `/login`; horizontal scaling requires a shared store (e.g. Redis). Acceptable for the single-instance v1.0 deployment topology. |
