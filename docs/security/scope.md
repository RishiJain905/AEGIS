# AEGIS Security Scope

AEGIS v1.0 is a defensive simulation and training platform. The release scope is
limited to synthetic scenarios, local test data, local containers, and controlled
operator workflows.

## Safety boundaries

- Do not connect the simulator to production infrastructure, production credentials,
  real customer data, or unapproved external targets.
- Scenario packages, telemetry, model output, and operator text are untrusted input.
  Validation, allowlists, structured contracts, and approval gates remain in force.
- Model suggestions are advisory. They cannot directly execute arbitrary commands,
  change real systems, or approve their own actions.
- The local production-like Compose stack is a staging stand-in only. Cloud deployment,
  registry publication, and external rollout are explicitly deferred under
  [ADR 0033](../AEGIS-v1.0-Agent-Specs/adrs/0033-deployment-readiness-without-executed-deployment.md).

## Defensive scope

In scope are secure local execution, authorization and approval behavior, auditability,
replay integrity, scenario/package validation, provider failure handling, dependency
and image scanning, and protection of secrets in logs and artifacts.

Offensive activity, real-world intrusion, credential testing against external systems,
and production operational guidance are out of scope.

## Reporting policy

Do not disclose a suspected vulnerability in a public issue with secrets, exploit code,
or sensitive traces. Report it privately to the repository security owner using the
organization's configured private security-reporting channel, or to the repository
owner if no private channel is available. Include affected commit/path, reproduction
steps, impact, and a minimal safe proof. Redact credentials and personal data.

The [scan triage policy](scan-triage-policy.md) defines severity handling, exception
records, ownership, and expiry. A scan result is not an approval to ship; blocking
findings require remediation or an approved, time-bounded exception.
