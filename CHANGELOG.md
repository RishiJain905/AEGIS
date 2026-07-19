# Changelog

Release history is grouped by the phase that introduced the capability. Version
identifiers describe repository artifacts; schema and protocol versions remain governed
by [contract versioning](docs/contracts/versioning.md).

## [1.0.0] - 2026-07-18

### Phase 35 - v1.0 release preparation

- Set repository package metadata and canonical workspace identifiers to `1.0.0`.
- Added release notes, checklist, schema-versioned release manifest generation and
  validation, deterministic Silent Relay demo metadata, and attribution-generation
  instructions.
- Finalized clean-machine setup, operator, provider, scenario-authoring, troubleshooting,
  security-scope, and contribution documentation.
- No cloud deployment, registry push, publication, or remote tag is part of this release
  preparation; see [ADR 0033](docs/AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md).

### Phase 34 - full-system validation

- Recorded offline, integration, golden, security, failure-injection, browser E2E, and
  release-validation evidence in `docs/release/evidence/`.
- Chromium E2E passed; Firefox and WebKit were skipped because their Playwright
  executables were not installed in the validation environment.
- Preserved the open web-image transitive HIGH findings and other known limitations in
  [known issues](docs/release/known-issues.md).

### Phases 30-33 - production readiness and deployment preparation

- Added release validation, local production-like Compose startup, deployment smoke
  checks, migration/rollback and backup/restore runbooks, security scanning policy,
  SBOM/license-report workflow references, and readiness evidence.
- The local production-like stack is the staging stand-in; cloud resources and image
  publication remain explicitly deferred.

### Phases 27-29 - cinematic, reporting, and after-action workflows

- Added cinematic presentation, report generation, scoring, and after-action review
  contracts and operator-facing workflows over recorded simulation evidence.

### Phases 24-26 - approvals, replay, and audit

- Added approval gates, deterministic replay/read models, audit persistence, and
  evidence-linked operator decisions.

### Phases 18-23 - model providers and agent system

- Added provider-neutral generation contracts, mock/recorded provider modes, resilience,
  structured-output validation, agent roles, action proposals, approval integration,
  and audit artifacts.

### Phases 14-17 - detection and ML evidence

- Added telemetry normalization, detection pipelines, model manifests and scores, and
  evidence-backed alert/incident workflows.

### Phases 11-13 - realtime and operational views

- Added event streaming, realtime client contracts, live graph projections, and
  observability foundations.

### Phases 08-10 - scenario and deterministic simulation

- Added declarative scenario SDK validation and packaging, deterministic simulation
  runtime, behavior-plugin allowlists, and Operation Silent Relay scenario content.

### Phases 05-07 - graph domain

- Added graph identity, topology, relationship, risk, traversal, and graph-domain
  contracts used by the simulator and web views.

### Phases 03-04 - product shell

- Added the API/web application shell, authentication and authorization boundaries,
  persistence foundation, and local development workflow.

### Phases 00-02 - repository and contract foundation

- Established the monorepo, Python/TypeScript package layout, shared contract ownership,
  schema generation, database migration baseline, CI verification, and engineering
  standards.

## Unreleased

No changes are recorded after `1.0.0` in this checkout.
