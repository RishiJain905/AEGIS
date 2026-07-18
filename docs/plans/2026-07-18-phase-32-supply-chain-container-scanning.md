# Phase 32 Supply-Chain and Container Scanning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden application containers and add local-only SBOM, SAST, Dockerfile, IaC, container, and license scanning with documented triage gates.

**Architecture:** Runtime hardening is expressed in the four application services in `docker-compose.yml`, with Dockerfiles declaring safe temporary-directory behavior. CI builds the same local Compose images, scans them through version-pinned scanner containers, stores CycloneDX/SARIF/license artifacts, and never authenticates to or publishes to a registry. Existing dependency and secret scans remain authoritative in `ci.yml`.

**Tech Stack:** Docker Compose, Dockerfiles, GitHub Actions, Semgrep, Hadolint, Trivy, Syft, CycloneDX JSON, SARIF, Markdown policy records.

---

### Task 1: Add container runtime hardening

**Files:**
- Modify: `apps/api/Dockerfile`
- Modify: `apps/web/Dockerfile`
- Modify: `services/workers/Dockerfile`
- Modify: `services/simulation/Dockerfile`
- Modify: `docker-compose.yml`

**Steps:**

1. Add explicit non-bytecode/unbuffered Python and `/tmp` environment behavior to Python runners and `/tmp`/telemetry environment behavior to the Node runner.
2. Preserve the existing non-root users and copy runtime files with the application user as owner where practical.
3. Add `read_only`, bounded `/tmp` tmpfs, `cap_drop: ALL`, and `no-new-privileges` to `api`, `web`, `worker`, and `simulator` only.
4. Comment/document the writable tmpfs and why stateful/observability infrastructure is not forced read-only.

### Task 2: Add CI security scanning workflow

**Files:**
- Create: `.github/workflows/security.yml`

**Steps:**

1. Add pinned checkout and artifact actions with `contents: read` permissions.
2. Add a Semgrep Python/TypeScript SAST job that fails on error-severity findings and uploads SARIF.
3. Add Hadolint for all four Dockerfiles with error-level gating and artifact output.
4. Add Trivy misconfiguration scans for Compose and all Dockerfiles with high/critical gating.
5. Add a local Compose build job for `api`, `web`, `worker`, and `simulator`; generate per-image CycloneDX SBOMs and scan fixable high/critical image vulnerabilities with Trivy.
6. Generate a dependency-manifest CycloneDX SBOM and a non-blocking license report from it; upload all reports regardless of scanner exit status.
7. Confirm the workflow has no audit/gitleaks duplication, registry push, deploy, or credential requirement.

### Task 3: Document triage and extend security models

**Files:**
- Create: `docs/security/scan-triage-policy.md`
- Modify: `docs/security/control-matrix.md`
- Modify: `docs/security/threat-model.md`

**Steps:**

1. Define scanner ownership, severity gates, fixable-vulnerability behavior, report retention, license triage, and the owner/expiry/justification exception-record contract.
2. Append continuing `SEC-016` through `SEC-020` controls for container runtime, SBOM, CI scanning, exception governance, and licensing.
3. Add build/supply-chain data flows, abuse paths `TM-010` onward, mitigations, detection ideas, and residual assumptions.

### Task 4: Validate without committing

**Steps:**

1. Parse `.github/workflows/security.yml` with `actionlint` or an available Node YAML parser.
2. Run `docker compose config`.
3. If Docker responds, build `api`, `web`, `worker`, and `simulator`.
4. Run `scripts/verify.sh` or `scripts/verify.ps1` and confirm the final line is `VERIFY: PASS`.
5. Inspect `git diff` and `git status --short --branch`; leave all changes uncommitted and report any unavailable checks precisely.
