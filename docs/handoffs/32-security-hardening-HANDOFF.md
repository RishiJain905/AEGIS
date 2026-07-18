# Phase 32 Handoff — Security Hardening

## Status

`READY FOR VALIDATION`

## Implemented

Threat-modeled and hardened the platform's trust boundaries per the Phase 32 specification, in two coordinated tracks:

**Trust-boundary core (SEC-001–SEC-015, TM-001–TM-009):**

- `docs/security/threat-model.md` — threat model + abuse cases for every trust boundary (browser→web, web→API, API→data services, WS gateway, agent runtime→tools, model-provider egress, scenario content→runtime, replay/report/export artifacts), each mapped to control IDs and tests.
- `docs/security/control-matrix.md` — control ID → boundary → implementation file(s) → test file(s) → status.
- API boundary (`apps/api/src/aegis_api/security/`): `SecurityHeadersMiddleware` (API CSP `default-src 'none'`, nosniff, DENY framing, no-referrer, HSTS gated on production + `AEGIS_SECURITY_HSTS_ENABLED`); `RequestBodyLimitMiddleware` (bounds bodies even with absent/dishonest Content-Length; structured `413 REQUEST_BODY_TOO_LARGE`); `TokenBucketRateLimitMiddleware` (deterministic in-process token buckets keyed by client IP and SHA-256-hashed session cookie, bounded LRU bucket table, structured `429 RATE_LIMIT_EXCEEDED` + Retry-After, health/readiness exempt). All reuse `ApiErrorEnvelopeV1` with stable codes and trace IDs.
- Web boundary: `apps/web/next.config.ts` `headers()` — CSP tuned for Next/Sigma/Three (documented decisions inline), X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-Frame-Options.
- Report export (`services/reports/src/aegis_reports/export.py`): all interpolated report/LLM-originated fields HTML-escaped; `load_template` traversal guard (resolve + root-prefix check). Closes a stored-XSS-shaped defect.
- Secrets: general fail-closed production startup validation (`apps/api/src/aegis_api/security/startup.py`) — required secrets present, dev placeholders from `.env.example` rejected in production; minimal env-backed secret-provider interface (`security/secrets.py`) behind an adapter for future secret managers; rotation guidance in `docs/security/secret-rotation.md`. Observability logging now reuses the model-provider recursive redaction (single redaction path, `packages/observability/src/aegis_observability/redaction.py` delegates).
- Model-provider egress (`packages/model-provider/src/aegis_model_provider/egress.py`): exact-match normalized destination allowlist (`AEGIS_PROVIDER_EGRESS_ALLOWLIST`) enforced at adapter construction; rejects credentials/query/fragment URLs; error responses do not disclose the destination.
- Agent/tool/scenario policy (`services/agents/security/` policies + `services/agents/src/aegis_agents/security/scenario_content.py`): three-layer tool authorization formalized (registry membership → execution-class exclusion → role∩agent allowlist); scenario-sourced prompt content is JSON-serialized, delimiter-escaped (cannot close its own data fence), size-bounded (32 KiB), schema-versioned, and delivered as user-role data only.

**Supply chain / containers / CI scanning (SEC-016–SEC-020, TM-010–TM-014):**

- Four app Dockerfiles + `docker-compose.yml`: read-only root filesystems with explicit tmpfs/volumes, `cap_drop: ALL`, `security_opt: no-new-privileges`, ownership fixes, refreshed OS packages. Local stack verified healthy under hardening.
- `.github/workflows/security.yml` (all actions SHA-pinned, no deploy/publish/push steps): Semgrep SAST, Hadolint, Trivy image + config scans of locally built images, Checkov (incl. custom compose-hardening policy `infra/security/checkov/compose_app_hardening.py`), CycloneDX SBOM artifacts, non-blocking license report.
- `docs/security/scan-triage-policy.md` — severity gates (fail on fixable HIGH/CRITICAL vulns, HIGH/CRITICAL IaC findings, Semgrep/Hadolint errors, SBOM failure) and the exception-record contract (owner, justification, remediation plan, approval, ≤30-day expiry).

## Files added

`apps/api/src/aegis_api/security/{__init__,middleware,secrets,startup}.py`; `docs/security/{threat-model,control-matrix,secret-rotation,scan-triage-policy}.md`; `packages/model-provider/src/aegis_model_provider/egress.py`; `services/agents/security/{egress-policy,scenario-content-policy,tool-security-policy}.md`; `services/agents/src/aegis_agents/security/{__init__,scenario_content}.py`; `.github/workflows/security.yml`; `infra/security/checkov/compose_app_hardening.py`; `tests/security/{test_api_hardening,test_report_export_hardening,test_startup_security,test_provider_egress,test_agent_policy_bypasses}.py`; `apps/web/tests (test_web_security_headers.test.ts)`; planning notes under `docs/plans/`.

## Files modified

`.env.example` (new security env vars), `apps/api/src/aegis_api/main.py` (middleware wiring), `apps/web/next.config.ts`, `apps/web/vitest.config.ts`, `packages/contracts-python/src/aegis_contracts/settings.py` (typed settings for new env vars), `packages/model-provider/{config,redaction,openai adapters}`, `packages/observability/redaction.py` (+ dependency on model-provider redaction), `services/agents/src/aegis_agents/runtime/executor.py` (scenario-content encoding at prompt assembly), `services/reports/src/aegis_reports/export.py`, four Dockerfiles, `docker-compose.yml`, `uv.lock`.

## Files removed

None.

## Contracts introduced or changed

- Egress policy (schema-versioned settings + normalization contract in `aegis_model_provider.egress`), scenario-content data-delimiter contract (`SCENARIO_CONTENT_SCHEMA_VERSION = 1`, 32 KiB bound), exception-record contract (documented in scan-triage-policy), new typed settings fields in `AegisSettings`. No existing durable event/API contract changed; all additions are additive and reuse Phase 01 primitives (`ApiErrorEnvelopeV1`, stable error codes).

## Database migrations

None.

## Environment and configuration changes

New env vars (documented in `.env.example` with safe dev defaults): `AEGIS_REQUEST_BODY_MAX_BYTES=1048576`, `AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE=120`, `AEGIS_RATE_LIMIT_BURST=30`, `AEGIS_RATE_LIMIT_MAX_BUCKETS=10000`, `AEGIS_SECURITY_HSTS_ENABLED=false`, `AEGIS_SECURITY_HSTS_MAX_AGE_SECONDS=31536000`, `AEGIS_PROVIDER_EGRESS_ALLOWLIST=https://api.openai.com/v1,http://localhost:11434/v1`.

## Generated artifacts and fixtures

CI now produces SBOM (CycloneDX), scan reports, and license-report artifacts on push; nothing is published externally.

## Tests added

- `tests/security/test_api_hardening.py` — headers present on all responses incl. error paths; HSTS production gating; dishonest/chunked body-limit rejection; rate limiting per IP and per hashed session incl. bucket-cap eviction; health exemptions.
- `apps/web` `test_web_security_headers.test.ts` — exact browser CSP/security-header policy.
- `tests/security/test_report_export_hardening.py` — XSS payloads encode inert; traversal/absolute template paths rejected.
- `tests/security/test_startup_security.py` — production boot fails on missing/placeholder/localhost config; provider precedence; shared redaction path.
- `tests/security/test_provider_egress.py` — arbitrary destinations, metadata IPs, suffix tricks, embedded credentials, empty allowlist all rejected.
- `tests/security/test_agent_policy_bypasses.py` — malicious model output cannot call unauthorized/execution-class tools (deterministic provider fakes + `fixtures/agent-workflows/unauthorized-*.json`); scenario delimiter-injection attempts stay inert; oversized scenario content rejected; WARDEN/approval final-revalidation cannot be bypassed.

All are bypass-attempt (negative-path) tests, not happy-path checks.

## Commands executed and results

- `scripts\verify.ps1` → all stages ok, final line `VERIFY: PASS` (952+ pytest passed incl. new security suites; vitest, eslint, tsc, prettier, ruff, mypy, import-linter, contracts all ok). Run independently by the orchestrator after both tracks landed.
- `docker compose config --quiet` → pass. `docker compose build api web worker simulator` → pass. API/web/worker containers verified healthy under the new hardening settings.
- Local scans executed for real (not just wired into CI): Semgrep, Hadolint (0 errors on all four Dockerfiles), Trivy (Dockerfile + image), Checkov — pass, except web-image transitive findings (below).
- Optional `-Build` note: Next.js production build compiles; Windows standalone packaging hits an OS-level symlink `EPERM` on this machine (pre-existing platform limitation; Linux CI builds are unaffected).

## Architecture decisions and ADRs

No ADR required. All decisions stay inside existing architecture rules: rate limiting is in-process (no new durable technology), egress control lives behind the existing model-provider adapter boundary, container/CI hardening changes no deployment shape, and no authorization boundary moved. Nothing in this phase modifies a non-negotiable rule from `architecture.md`.

## Known limitations

- Web container image retains 23 fixable HIGH transitive Node findings; recorded for triage per `docs/security/scan-triage-policy.md` (time-bounded exception mechanism) rather than blind-bumping pinned dependencies mid-phase.
- Rate limiting is per-process (by design — modular monolith); multi-replica deployments share no bucket state. Documented in the control matrix.
- HSTS requires explicit production enablement (TLS termination is a Phase 33 deployment concern).
- Windows-local `pnpm build` standalone packaging EPERM (symlinks); does not affect CI or the verify gate.

## Deferred work

- Session lockout/backoff on repeated auth failures (candidate for review-phase finding; not in spec's minimum set).
- Signed private-object URLs: object access is API-mediated by design; signing deferred until a direct-download product need exists.

## Risks for dependent phases

- Phase 33 must preserve `cap_drop`/read-only-root/tmpfs settings in any generated deployment manifests, keep the security workflow deploy-free, and respect the egress allowlist env contract when defining environment templates.
- New env vars must appear in Phase 33 environment contracts and Phase 35 configuration docs.
- CSP for the web app allows what Sigma/Three need; any renderer change (Phase 32+ Three.js work) must be re-verified against the CSP rather than loosening it casually.

## Acceptance criteria evidence

- *Threats map to implemented controls and tests* — `docs/security/threat-model.md` + `control-matrix.md` map TM-001–TM-014 → SEC-001–SEC-020 → implementation + test files.
- *Scenario/model content cannot bypass policy or tool authorization* — `test_agent_policy_bypasses.py` (injection, unauthorized-tool fixtures, oversized content, WARDEN/approval revalidation) passes.
- *Agents cannot reach arbitrary network/filesystem/execution* — execution-class tools categorically uncallable (`authorize_tool_call`), egress allowlist enforced at adapter construction (`test_provider_egress.py`), no filesystem/network tools exposed to models.
- *Critical findings fixed or explicitly excepted* — local scans pass at the configured gates; the one open item (web transitive HIGHs) is recorded under the documented time-bounded exception contract.

## Prohibited-shortcut confirmation

No tests were deleted, skipped, loosened, or rewritten to pass; no scaffolding-only deliverables; no duplicate domain types (redaction consolidated to one path rather than duplicated); security is server-enforced; no mocks on production paths; all validation commands were actually executed on this tree.
