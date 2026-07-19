# AEGIS Terraform deployment shape

The three environment directories (`dev`, `staging`, and `production`) are
offline, provider-neutral templates. They use Terraform's built-in
`terraform_data` resource to describe the intended runtime, private data
services, secret-manager references, HTTPS edge, telemetry, and backup shape.
`terraform_data` does not contact a provider or create infrastructure. This is
intentional for Phase 33: cloud activation is explicitly deferred by ADR 0033.

The module inputs contain names and policy settings only. Secret values,
provider credentials, state files, domains, DNS records, and object-storage
contents are not represented in this repository.

Validate each environment offline:

```bash
terraform -chdir=infra/terraform/environments/dev fmt -check
terraform -chdir=infra/terraform/environments/dev init -backend=false -input=false
terraform -chdir=infra/terraform/environments/dev validate

terraform -chdir=infra/terraform/environments/staging fmt -check
terraform -chdir=infra/terraform/environments/staging init -backend=false -input=false
terraform -chdir=infra/terraform/environments/staging validate

terraform -chdir=infra/terraform/environments/production fmt -check
terraform -chdir=infra/terraform/environments/production init -backend=false -input=false
terraform -chdir=infra/terraform/environments/production validate
```

Before a future activation task, an owner-approved provider adapter must replace
the `terraform_data` inventory with provider resources while preserving these
module inputs. That task must choose a remote backend, enable encryption and
state locking, restrict state access, and configure the backend through local
or CI environment variables. No backend block, remote-state key, access key,
credential, or state file belongs in this repository.

Provider substitution must retain these invariants:

- the container runtime reaches the API/web/worker/simulator images by immutable
  artifact references;
- PostgreSQL, Redis, and object storage are private and reachable only from the
  runtime network;
- secrets are secret-manager references, never Terraform values or outputs;
- TLS terminates at an HTTPS edge before public traffic reaches the runtime;
- worker/provider egress stays allowlisted and telemetry remains fail-open for
  domain correctness; and
- backups, migration jobs, rollout gates, and restore rehearsals are explicit
  operational steps, not implicit Terraform side effects.
