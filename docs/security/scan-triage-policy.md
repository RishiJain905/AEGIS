# AEGIS Security Scan Triage Policy

This policy governs the build-time security controls introduced by Phase 32. It applies to pull requests and branch builds that run the repository security workflows. The scans build local images only; they do not require cloud credentials and never push or publish an image.

## Scanner ownership and report location

`.github/workflows/ci.yml` remains authoritative for `pnpm audit`, `pnpm audit signatures`, `pip-audit`, and gitleaks. `.github/workflows/security.yml` owns Semgrep SAST, Hadolint, Trivy IaC/Compose checks, local application-image vulnerability scans, CycloneDX SBOMs, and the derived license report. These checks are intentionally not duplicated across workflows.

GitHub Actions are pinned to commit SHAs. Scanner containers are pinned to version tags plus immutable image digests; changing either the tool version or digest is a reviewed control change.

The workflow uploads SARIF, CycloneDX, and license reports as the `security-*` artifacts for 14 days. A finding is tracked in the pull request that introduced or exposes it and in a GitHub issue labeled `security-scan` when remediation spans more than one pull request. The issue or PR must link to the artifact, scanner rule/advisory, affected path or image, and the proposed remediation. The repository's existing security control matrix remains the durable map from findings to controls.

## Severity gates

| Scanner | Blocking condition | Treatment of other findings |
| --- | --- | --- |
| Trivy image vulnerability scan | A fixable `HIGH` or `CRITICAL` OS/library vulnerability in an application image. The workflow uses `--ignore-unfixed` and `--severity HIGH,CRITICAL`. | Unfixed high/critical findings are still recorded for review and should be addressed by a base/dependency refresh or an approved exception. Medium/low findings are backlog items unless an exploit or asset context raises their priority. |
| Trivy Compose/IaC scan | A `HIGH` or `CRITICAL` misconfiguration in the scanned repository. | Medium/low findings are reported and triaged without blocking this gate. |
| Semgrep | An `ERROR`-severity Python or TypeScript finding. This is the SAST equivalent of a high/critical code defect for this workflow. | Warning/info findings are retained in the SARIF artifact and triaged in the owning PR or issue. |
| Hadolint | An error-level Dockerfile lint finding. | Warnings and style findings are reported but do not block this security gate; security-relevant warnings may be promoted by the reviewer. |
| SBOM generation | Failure to build an application image or generate an image/dependency CycloneDX SBOM. | No scan result is treated as a pass. The failed job is fixed or explicitly escalated. |
| License report | None. The report is non-blocking in this phase. | Unknown, missing, prohibited, or newly introduced licenses are tracked for legal/owner review before release and must not be silently ignored. |

The required release decision is: fix every blocking finding, or attach an approved, unexpired exception record. A green result from another job does not override a failed security gate.

## Current local baseline requiring triage

The local Phase 32 scan on 2026-07-18 used Trivy `0.61.0` against freshly rebuilt `aegis-security-api`, `aegis-security-web`, `aegis-security-worker`, and `aegis-security-simulator` images with `--ignore-unfixed --severity HIGH,CRITICAL`. Refreshing the Debian and Alpine OS packages in the runner stages removed all gated OS findings from API, worker, and simulator and removed the web image's critical OS findings. The remaining result is:

| Asset | Result | Finding group | Deferred action |
| --- | --- | --- | --- |
| `aegis-security-web:latest` local image | 0 critical, 23 fixable high (11 unique CVEs) | Transitive Node packages: `glob@10.4.5`, `minimatch@9.0.5`, `sigstore@3.0.0`, and `tar@6.2.1`/`7.4.3`; the complete CVE set is `CVE-2025-64756`, `CVE-2026-26996`, `CVE-2026-27903`, `CVE-2026-27904`, `CVE-2026-48815`, `CVE-2026-23745`, `CVE-2026-23950`, `CVE-2026-24842`, `CVE-2026-26960`, `CVE-2026-29786`, and `CVE-2026-31802` (confirmed against `trivy-image-web.sarif`; api/worker/simulator are clean) | Dependency owner refreshes the base image / npm toolchain so it resolves `glob>=10.5.0`, `minimatch>=9.0.6`, `sigstore>=4.1.1`, and `tar>=7.5.11`, tracked in a `security-scan` issue/PR. Until then the finding is covered by the time-bounded exception below. |

These 11 CVEs are all in **transitive Node tooling packages** (`glob`, `minimatch`, `sigstore`, `tar`) that enter the web image through the npm/pnpm toolchain, not the application's own dependency graph, and are not reachable from AEGIS request paths (build-time archive/glob/signature tooling only).

### EXC-2026-0001 — web-image transitive Node tooling HIGH advisories

- Finding ID: Trivy image scan — `CVE-2025-64756`, `CVE-2026-26996`, `CVE-2026-27903`, `CVE-2026-27904`, `CVE-2026-48815`, `CVE-2026-23745`, `CVE-2026-23950`, `CVE-2026-24842`, `CVE-2026-26960`, `CVE-2026-29786`, `CVE-2026-31802`
- Severity and fixability: HIGH; all fixable (fixed versions listed above). Report: `security-container-supply-chain` artifact → `trivy-image-web.sarif`.
- Affected asset: `aegis-security-web:latest` local image (transitive `glob@10.4.5`, `minimatch@9.0.5`, `sigstore@3.0.0`, `tar@6.2.1`/`7.4.3`).
- Owner: Rishi Jain (release owner, v1.0).
- Expiry: 2026-08-18T00:00:00Z (30 calendar days, policy maximum).
- Justification: findings are in the npm/pnpm toolchain bundled in the image, not app dependencies; no app lockfile edit resolves them. A base-image/toolchain refresh is the correct fix and cannot land under the v1.0 release gate window.
- Compensating controls: images are build-and-scan only and never published; web container runs as a non-root user over a read-only app tree; no untrusted archive extraction or glob expansion on request paths.
- Remediation plan: refresh base image / npm toolchain to pull the fixed versions above; tracked in the `security-scan` issue linked from PR #34.
- Approver and approval date: Rishi Jain, 2026-07-19.
- Status: active.

This exception is enforced by [`.trivyignore.yaml`](../../.trivyignore.yaml) at the repo root, which the `Local image scan and SBOM` gate passes to Trivy via `--ignorefile`. Each entry carries `expired_at: 2026-08-18`; on that date Trivy stops honoring the entry and the gate fails again until the finding is fixed or the exception is re-approved. New HIGH/CRITICAL findings outside this CVE list are not covered and still fail the gate. The local report files are diagnostic artifacts and are not committed.

## Triage service levels

- `CRITICAL`: contain and assign within 24 hours; remediate or obtain an exception before the next release candidate.
- `HIGH`: assign within two business days; remediate within seven calendar days unless an exception is approved.
- `MEDIUM`: assign within ten business days and resolve in the normal maintenance window.
- `LOW` or informational: retain in the report/backlog and review during dependency or base-image maintenance.

These targets are response targets, not permission to leave a blocking finding open. An exception expiry is the hard deadline.

## Exception record contract

An exception is a narrow, finding-specific risk acceptance. It must be approved by the security owner or release owner before the gate is bypassed. Scanner configuration changes, blanket path exclusions, and lowering a severity threshold are not exception records.

Every exception record must contain all of these fields:

| Field | Required content |
| --- | --- |
| Finding ID | Scanner plus stable rule/advisory ID, for example `Trivy-CVE-YYYY-NNNN` or `Semgrep-rule-id`. |
| Severity and fixability | Current severity, whether a fixed version exists, and the scanner report link. |
| Affected asset | Image digest/tag, dependency, Dockerfile, Compose service, or source path. |
| Owner | One named engineering owner accountable for remediation. A team alias alone is insufficient. |
| Expiry | ISO-8601 UTC date/time. Maximum duration is 30 calendar days; `CRITICAL` exceptions should be shorter and cannot cross a release without re-approval. |
| Justification | Concrete reason remediation cannot be completed before the gate, including compatibility or vendor constraints. “False positive” requires evidence. |
| Compensating controls | Specific controls that reduce likelihood or impact during the exception. |
| Remediation plan | Exact next action, target version/change, and linked issue or pull request. |
| Approver and approval date | Named security/release approver and ISO-8601 approval date. |
| Status | `active`, `expired`, `remediated`, or `rejected`. |

Use this template for an active record in the pull request or linked issue:

```markdown
### EXC-YYYY-NNNN — <short finding title>

- Finding ID: <scanner/rule/advisory>
- Severity and fixability: <critical/high/...>; <fixable/unfixed>
- Affected asset: <image digest, dependency, path, or service>
- Owner: <named person>
- Expiry: <YYYY-MM-DDTHH:MM:SSZ>
- Justification: <specific evidence>
- Compensating controls: <specific controls>
- Remediation plan: <action, target, issue/PR link>
- Approver and approval date: <name>, <YYYY-MM-DD>
- Status: active
```

The active exception record must remain linked from the finding issue/PR. On expiry, the gate fails again until the finding is fixed or a new record is approved; extensions are new approvals, not silent date edits.

## License triage

The CycloneDX-derived license report is a visibility control, not a legal determination. The owner reviews new or unknown SPDX identifiers, missing license metadata, and licenses incompatible with the product's distribution model. Legal or release-owner approval is required before shipping a newly introduced restricted or unknown license. The review decision and any follow-up issue are recorded with the pull request; no license is made “approved” solely because the scanner did not block.

## Change control

Changes to scanner versions, rulesets, severity flags, ignored paths, or exception policy require a reviewed pull request and an update to the relevant `SEC-016`–`SEC-020` control evidence. A scanner outage or unavailable Docker daemon is a validation failure to report, not a reason to weaken a gate.
