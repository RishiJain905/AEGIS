# Phase 32 Supply-Chain and Container Scanning Design

## Goal

Implement the supply-chain, container-hardening, SBOM, and CI-scanning half of AEGIS Phase 32 without changing application behavior or the existing trust-boundary implementation.

## Design

- Harden the four application images at runtime through Compose: read-only root filesystems, a bounded writable `/tmp` tmpfs, all Linux capabilities dropped, and `no-new-privileges`. The Dockerfiles set explicit temporary-directory and Python runtime behavior and preserve the existing pinned multi-stage, non-root layout.
- Leave stateful and observability infrastructure writable where their data volumes or runtime assumptions require it. The Compose comments and security documentation identify the writable paths and the infrastructure exception.
- Add `.github/workflows/security.yml` with pinned checkout/artifact actions and scanner CLIs run as version-pinned containers. The workflow builds only local application images, produces CycloneDX SBOM artifacts, scans images with Trivy, lints Dockerfiles with Hadolint, scans Compose/Dockerfiles with Trivy config, and runs Semgrep for Python/TypeScript SAST. It has no credentials, registry push, or deployment step.
- Keep dependency audits and gitleaks in the existing CI workflow. The new workflow does not duplicate them; its license report is derived from the generated dependency SBOM and is explicitly non-blocking.
- Add a severity/triage contract with short-lived, owner-assigned exceptions and extend the control matrix/threat model with the new container and supply-chain boundary IDs.

## Validation

Run `docker compose config`, build the four application images when a Docker daemon is available, parse the workflow YAML with an available YAML/actionlint validator, run the repository verification script, and inspect the final diff/status. All changes remain uncommitted on the current checkout.
