# Phase 32 Trust-Boundary Core Implementation Plan

> **For Codex:** Implement task-by-task with test-first red/green cycles. Do not commit; the owner requested an uncommitted working tree.

**Goal:** Harden AEGIS runtime trust boundaries without changing deployment shape or adding infrastructure.

**Architecture:** Enforce HTTP limits and headers in reusable ASGI middleware, validate production configuration before dependency startup, constrain provider destinations at adapter construction, and preserve the existing WARDEN/tool/approval enforcement points. Treat scenario and model content as untrusted data, encode report HTML at export, and document every control with test evidence.

**Tech Stack:** Python 3.12, FastAPI/Starlette ASGI, Pydantic Settings, Next.js, pytest/Vitest, existing AEGIS contracts/policy/provider/report packages.

---

### Task 1: API boundary middleware

**Files:**

- Create: `tests/security/test_api_hardening.py`
- Create: `apps/api/src/aegis_api/security/middleware.py`
- Modify: `apps/api/src/aegis_api/main.py`
- Modify: `packages/contracts-python/src/aegis_contracts/settings.py`
- Modify: `.env.example`

1. Add failing tests for CSP/security headers, conditional HSTS, structured 413 errors, deterministic token-bucket 429 errors, and health/readiness exemptions.
2. Run `uv run pytest tests/security/test_api_hardening.py -q` and confirm failures are caused by missing middleware/settings.
3. Implement minimal ASGI middleware and wire it around the app.
4. Re-run the focused tests until green.

### Task 2: Report export boundary

**Files:**

- Create: `tests/security/test_report_export_hardening.py`
- Modify: `services/reports/src/aegis_reports/export.py`

1. Add failing stored-XSS and path-traversal tests.
2. Run the focused test and confirm raw markup/traversal currently succeeds.
3. Escape every HTML interpolation and constrain template paths to the report template root.
4. Re-run until green.

### Task 3: Production secrets and shared redaction

**Files:**

- Create: `tests/security/test_startup_security.py`
- Create: `apps/api/src/aegis_api/security/secrets.py`
- Create: `apps/api/src/aegis_api/security/startup.py`
- Modify: `apps/api/src/aegis_api/main.py`
- Modify: `packages/model-provider/src/aegis_model_provider/redaction.py`
- Modify: `packages/observability/src/aegis_observability/redaction.py`
- Modify: `packages/observability/pyproject.toml`

1. Add failing tests for missing/placeholder production secrets, secret-name-only errors, provider substitution, and observability reuse of canonical redaction.
2. Implement the secret-provider protocol, environment adapter, composite startup gate, and model-provider-owned redaction functions.
3. Re-run startup/redaction and existing observability/provider tests until green.

### Task 4: Provider egress and agent content/tool policy

**Files:**

- Create: `tests/security/test_agent_policy_bypasses.py`
- Create: `tests/security/test_provider_egress.py`
- Create: `services/agents/src/aegis_agents/security/scenario_content.py`
- Modify: `services/agents/src/aegis_agents/runtime/executor.py`
- Create: `packages/model-provider/src/aegis_model_provider/egress.py`
- Modify: provider settings and OpenAI-compatible adapters
- Add: `services/agents/security/*.md`

1. Add failing bypass tests using deterministic malicious provider output and the existing unauthorized workflow fixtures.
2. Add failing WARDEN/final approval revalidation tests and exact destination allowlist tests.
3. Implement scenario-data delimiting and adapter-construction egress validation while retaining all existing tool/approval enforcement layers.
4. Re-run focused policy/provider tests until green.

### Task 5: Web boundary and security documentation

**Files:**

- Modify: `apps/web/next.config.ts`
- Create: `docs/security/threat-model.md`
- Create: `docs/security/control-matrix.md`
- Create: `docs/security/secret-rotation.md`

1. Add Next.js response headers with a documented CSP exception for framework hydration/styles.
2. Write a repository-grounded threat model covering every required trust boundary.
3. Map stable control IDs to implementation paths and bypass tests.

### Task 6: Verification and handoff evidence

1. Run `scripts\verify.ps1 -TestPath tests/security` (or the supported equivalent) and repair failures without weakening tests.
2. Run focused existing agent, policy, approval, provider, observability, and report suites.
3. Run `scripts\verify.ps1` and require a final `VERIFY: PASS` line.
4. Audit `git diff`/`git status`, confirm no container/workflow files changed, and report exact evidence and deliberate deferrals.
