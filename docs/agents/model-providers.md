# Phase 18 — Model Provider Abstraction

> Canonical provider-neutral LLM interface for AEGIS agent phases 19+.

## Scope

Phase 18 delivers:

- Canonical generation contracts in `aegis_contracts.generation`
- `aegis_model_provider` package with registry, resilience, structured-output validation, and adapters
- Mock and recorded providers for deterministic CI
- Optional hosted OpenAI and local OpenAI-compatible adapters
- PostgreSQL `generation_artifacts` audit persistence
- API harness at `/providers/observability`

Phase 18 does **not** implement agent runtime, tool execution, approval workflows, or simulator mutations.

## Canonical interface

All model access must go through `GenerationService.generate(GenerationRequestV1)`.

Adapters implement `ModelProvider`:

- `provider_id`
- `capabilities() -> ProviderCapabilitiesV1`
- `async generate(request) -> GenerationResponseV1`

Provider SDK types must remain inside `aegis_model_provider.adapters.*`.

## Providers

| ID | Purpose | CI default |
|----|---------|------------|
| `mock` | Deterministic structured responses | Yes |
| `recorded` | Fixture replay from `fixtures/model-responses/` | Yes |
| `openai` | Hosted OpenAI API | Optional |
| `openai-compatible` | Local Ollama/vLLM endpoint | Optional |

## Configuration

See `.env.example` variables prefixed with `AEGIS_PROVIDER_`.

`AEGIS_PROVIDER_DEFAULT=mock` ensures core CI needs no external inference.

## Structured output

Model output is untrusted. JSON is parsed and validated against `StructuredOutputSpecV1` using `jsonschema`. A bounded repair attempt may run when `maxRepairAttempts > 0`.

## Errors

Normalized `ProviderErrorCode` values include `CREDENTIALS_MISSING`, `TIMEOUT`, `RETRY_EXHAUSTED`, `CIRCUIT_OPEN`, `STRUCTURED_OUTPUT_INVALID`, and `CAPABILITY_UNSUPPORTED`.

## Commands

```bash
uv run python scripts/run_provider_harness.py
uv run pytest tests/agents/provider-conformance -q
```

## Phase 19 constraints

- Import `GenerationService` via `aegis_agents.providers.create_generation_service`
- Do not import vendor SDKs in agent role implementations
- Persist agent outputs as artifacts; never write model output directly to simulation state
