# ADR 0019: Model Provider Abstraction (Phase 18)

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 19+ agent runtime requires a provider-neutral LLM interface with deterministic CI, bounded retries, structured-output validation, audit persistence, and strict adapter boundaries. Phase 18 must not implement agent orchestration.

## Decision

1. **Contracts:** LLM generation contracts live in `aegis_contracts.generation` (distinct from ML `models.py`).

2. **Package boundary:** `aegis_model_provider` owns adapters, resilience, structured-output validation, and orchestration. Vendor SDK imports are confined to `adapters/openai_*.py`.

3. **Providers:**
   - `mock` — default for CI/local harness
   - `recorded` — versioned fixtures under `fixtures/model-responses/`
   - `openai` — hosted adapter
   - `openai-compatible` — local endpoint adapter

4. **Resilience:** Uniform timeout, bounded exponential backoff retry, circuit breaker, and concurrency semaphore wrap all providers.

5. **Structured output:** Validate with `jsonschema`; allow at most `maxRepairAttempts` (default 1) repair re-prompt.

6. **Persistence:** `generation_artifacts` PostgreSQL table stores sanitized request/response metadata. Secrets are redacted before persistence.

7. **Security:** Missing credentials fail closed with `CREDENTIALS_MISSING` without leaking secret values.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Direct OpenAI calls from agent services | Violates architecture adapter rule |
| Reuse ML `ModelScore` contracts | Different semantics; would confuse anomaly vs LLM generation |
| External LLM required in CI | Violates architecture LLM-independence rule |

## Consequences

- Phase 19 must consume `GenerationService` only through `aegis_agents.providers`
- Streaming deferred to later phase
- Cost fields are audit estimates, not billing authority

## Approval

- [ ] Project owner
