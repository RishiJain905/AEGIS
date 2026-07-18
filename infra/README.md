# infra

Infrastructure definitions, compose overrides, and deployment helpers.

Phase 00: shared Docker and local development configuration references.

Phase 33: the provider-neutral Terraform deployment shape is documented in
[`terraform/README.md`](terraform/README.md). It uses built-in inventory
resources only; no provider, backend, credentials, or state are present.
