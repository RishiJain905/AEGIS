# v1.0.0 Release Checklist

Run every command from the repository root. Record output or a linked artifact for each
item. A checklist item is not complete because a neighboring command passed.

## Scope and version

- [ ] Confirm the checkout is `goal/v1.0-release`: `git branch --show-current`.
- [ ] Confirm all intended changes are reviewable and uncommitted: `git status --short`.
- [ ] Confirm version identifiers are `1.0.0`: `rg '0\.0\.0|WORKSPACE_VERSION|SDK_VERSION' package.json apps packages services pyproject.toml docs scripts`.
- [ ] Confirm the release identity and compatibility matrix in [v1.0.0 release notes](v1.0.md).

## Verification and release validation

- [ ] Run `.\scripts\verify.ps1`; retain the exact final line `VERIFY: PASS`.
- [ ] Run `.\scripts\run_release_validation.ps1 -Environment local`; retain the exact final line `RELEASE VALIDATION: PASS` and the generated evidence manifest under `docs/release/evidence/`.
- [ ] Confirm the latest evidence manifest has `environment: local`, `status: passed`, and links all command logs; cross-check the [Phase 34 evidence](../handoffs/34-full-system-validation-HANDOFF.md).
- [ ] Run `uv run pytest tests/release/test_release_manifest.py -q`.
- [ ] Run `uv run python scripts/generate_release_manifest.py --output release/manifest.json`; then run `uv run python scripts/verify_release_manifest.py release/manifest.json` and retain `RELEASE MANIFEST: PASS`.

## Artifacts and images

- [ ] Confirm `release/manifest.json` validates against `release/manifest.schema.json`, records the source revision, migration head, scenario checksum, model references, SBOM references, image inspect data, and checksums.
- [ ] Build local application images with `docker compose build api web worker simulator`; inspect them with `docker inspect`. Do not push them to a registry.
- [ ] Confirm model and scenario artifact checksums with the manifest verifier.
- [ ] Generate attribution from the CI CycloneDX/license report tooling:
  `uv run python scripts/generate_third_party_attribution.py --input <security-artifacts/license-report.json> --output THIRD-PARTY.md`.
- [ ] Review [THIRD-PARTY.md](../../THIRD-PARTY.md). A missing CI report is a release blocker for a published distribution, not evidence that licenses are approved.

## Documentation and clean machine

- [ ] In a fresh clone, copy `.env.example` to `.env`, run `pnpm install --frozen-lockfile`, run `uv sync --frozen --all-packages`, and run `.\scripts\verify.ps1` as described in [Getting Started](../getting-started.md).
- [ ] Run `uv run python scripts/demo_v1.py --headless` against the local stack and confirm the deterministic seed and URLs are printed.
- [ ] Confirm the docs point only to existing files and commands; retain any doc-vs-reality gap and its fix in the Phase 35 handoff.

## Safety, support, and deferred work

- [ ] Review [known issues](known-issues.md), the [security scope](../security/scope.md), and the [scan triage policy](../security/scan-triage-policy.md); do not hide or silently waive findings.
- [ ] Confirm migration status is `013_auth_identity`: `uv run alembic heads`.
- [ ] Confirm cloud deployment, registry push, publication, and cloud-scale load testing are explicitly `N/A` for this phase under [ADR 0033](../AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md).
- [ ] Local git tag `v1.0.0`: orchestrator action after review; not performed by Phase 35 implementation.
- [ ] Confirm support pointers in [Getting Started](../getting-started.md), [Operator Guide](../operator-guide.md), and [Troubleshooting](../troubleshooting.md).
