# Agent Model-Provider Egress Policy v1

## Ownership and scope

The model-provider package owns enforcement. Agent code selects a configured provider ID; it cannot supply a destination URL per request. Mock and recorded providers perform no network egress.

## Contract

- Configuration: `AEGIS_PROVIDER_EGRESS_ALLOWLIST`, a comma-separated set of exact HTTP(S) base URLs.
- Enforcement point: construction of `OpenAIHostedProvider` and `OpenAICompatibleProvider` through `assert_provider_destination_allowed`.
- Normalization: scheme and host are case-normalized and a trailing slash is ignored. Paths otherwise remain exact.
- Rejected forms: non-HTTP(S) schemes, userinfo/embedded credentials, query strings, fragments, empty allowlists, host suffix lookalikes, and any non-exact destination.
- Failure: fail closed with the canonical provider error envelope and stable `VALIDATION_FAILED` code. Errors identify the provider, not the rejected URL or credentials.
- Versioning: this is an in-process policy contract, version 1. No durable IDs, timestamps, or error envelopes are redeclared.

Provider requests remain bounded by the existing timeout, retry, concurrency, output-token, cost, and circuit-breaker settings. An allowlisted destination is not authorization to expose arbitrary tools or scenario state.
