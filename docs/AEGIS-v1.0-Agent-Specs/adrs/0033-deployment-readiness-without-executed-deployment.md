# ADR 0033: v1.0 ships deployment-ready artifacts without an executed cloud deployment

## Status

Accepted (project-owner directive, Phase 33 implementation)

## Context

The Phase 33 specification ("Cloud Deployment") assumes provisioning one
official managed-cloud staging target, executing deployments through CI/CD,
and rehearsing backup restore and rollback in that staging environment. The
project owner has directed, for the v1.0 goal, that no real cloud
infrastructure may be provisioned: no paid resources, no domains or DNS
changes, no hosted databases/Redis/object storage, no external container
registry pushes, no production credentials, and no workflow that deploys.
AEGIS must remain fully usable locally through Phase 35.

## Decision

1. Phase 33 is implemented as **deployment readiness**: production-grade
   container images, a production-like local Compose profile used as the
   validation stand-in for staging, cloud-neutral IaC templates validated
   offline (`terraform fmt -check`, `terraform validate` with no remote state
   or providers requiring credentials), environment-variable contracts,
   secret-management and networking/TLS requirements as documentation,
   backup/restore, migration, and rollback runbooks, and CI workflows that
   build, test, scan, and validate artifacts **and stop there** — any deploy
   job is absent or permanently gated behind manual approval environments that
   do not exist in this repository.
2. The spec's staging-dependent acceptance criteria are satisfied in their
   readiness form: "staging reproducible from IaC" becomes "staging is fully
   described by IaC + runbooks and validated offline"; "rollback rehearsed in
   staging" becomes "rollback rehearsed against the local production-like
   stack and documented step-by-step".
3. Executing a real deployment is deferred to a future explicitly-approved
   task after manual review of these artifacts.

## Consequences

- v1.0 can be released and operated locally; cloud activation is a documented,
  reviewable follow-up rather than an implemented pipeline.
- The deploy smoke test targets the local production-like stack; its
  environment flag accepts a future staging value without code change.
- Phase 34 validates the local production-like stack as the system-of-record
  environment; Phase 35 documents deployment readiness rather than a hosted
  release.
- Risk: real-cloud behavior (managed-service quirks, IAM, TLS termination)
  remains unexercised until the deferred activation task; this is accepted by
  the owner directive and recorded in the Phase 33 handoff.
