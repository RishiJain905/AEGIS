# Phase 18 Handoff — Model Provider Abstraction

## Status

`READY FOR VALIDATION`

## Implemented

Phase 18 deliverables per `docs/AEGIS-v1.0-Agent-Specs/agent-system/18-model-provider-abstraction.md`:

- Canonical generation contracts (`GenerationRequestV1`, `GenerationResponseV1`, `StructuredOutputSpecV1`, `ProviderUsageV1`, `ProviderErrorV1`, `RecordedResponseKeyV1`, `GenerationArtifactV1`, API DTOs)
- `aegis_model_provider` package with `ModelProvider` protocol, registry, `GenerationService`, resilience (timeout/retry/circuit breaker/concurrency), structured-output validation, redaction, cost estimation
- Adapters: `mock`, `recorded`, `openai` (hosted), `openai-compatible` (local)
- PostgreSQL `generation_artifacts` migration `005_generation_artifacts`
- `services/agents/providers` factory and facade for Phase 19
- API routes `/api/v1/providers/*` and observability harness `/providers/observability`
- Recorded fixtures under `fixtures/model-responses/`
- Conformance, unit, and security tests
- ADR 0019, `docs/agents/model-providers.md`
- Demo harness `scripts/run_provider_harness.py` and screenshot capture `apps/web/scripts/capture-provider-demo.mjs`

**Explicitly not implemented:** Agent runtime state machine, tool registry execution, approval workflows, agent roles, simulator mutations (Phase 19+).

## Files added

| Area | Key paths |
|------|-----------|
| Contracts | `packages/contracts-python/src/aegis_contracts/generation.py`, `packages/contracts-ts/src/generation.ts` |
| Provider package | `packages/model-provider/src/aegis_model_provider/**` |
| Persistence | `migrations/versions/005_generation_artifacts.py`, `GenerationArtifactRow`, `PostgresGenerationArtifactRepository` |
| Service wiring | `services/agents/src/aegis_agents/providers/**` |
| API | `apps/api/src/aegis_api/providers/**` |
| Fixtures | `fixtures/model-responses/**`, contract golden fixtures |
| Tests | `tests/agents/provider-conformance/**`, `tests/unit/model_provider/**` |
| Docs | `docs/agents/model-providers.md`, ADR `0019-model-provider-abstraction.md` |
| Scripts | `scripts/run_provider_harness.py`, `apps/web/scripts/capture-provider-demo.mjs` |

## Files modified

| File | Reason |
|------|--------|
| `packages/contracts-python/src/aegis_contracts/primitives.py` | Added `gen_` runtime ID prefix |
| `packages/contracts-python/src/aegis_contracts/versioning.py` | Phase 18 schema versions, `WORKSPACE_VERSION` bump |
| `packages/contracts-ts/src/versioning.ts`, `primitives.ts`, `index.ts` | TS mirror |
| `pyproject.toml`, `package.json` | Workspace wiring |
| `.env.example` | Provider configuration |
| `apps/api/src/aegis_api/main.py` | Register provider routers |
| `apps/api/pyproject.toml` | Depend on `aegis-agents` |

## Files removed

None.

## Contracts introduced or changed

| Contract | Version | Notes |
|----------|---------|-------|
| `GenerationRequestV1` / `GenerationResponseV1` | schema v1 | Canonical provider-neutral generation |
| `StructuredOutputSpecV1` | schema v1 | JSON Schema + bounded repair |
| `ProviderUsageV1` / `ProviderErrorV1` | schema v1 | Audit and normalized failures |
| `RecordedResponseKeyV1` | schema v1 | Deterministic fixture lookup |
| `GenerationArtifactV1` | schema v1 | Sanitized audit records |
| `ProviderGenerateRequestV1` / `ProviderGenerateResponseV1` | schema v1 | HTTP harness DTOs |
| `WORKSPACE_VERSION` | `0.0.0-phase18` | Compatibility bump |

## Database migrations

- `005_generation_artifacts.py` — `generation_artifacts` table

## Environment and configuration changes

Provider settings via `AEGIS_PROVIDER_*` (see `.env.example`). `AEGIS_PROVIDER_DEFAULT=mock` for CI. Optional `AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS=true` for harness without PostgreSQL.

## Generated artifacts and fixtures

- `fixtures/model-responses/manifest.json` and recorded responses
- `tests/contract/fixtures/valid/*generation*`, `*provider*`
- JSON schemas under `tests/contract/fixtures/schemas/`
- Screenshots under `/opt/cursor/artifacts/screenshots/18-*.png`

## Tests added

| Test | Proves |
|------|--------|
| `test_provider_conformance.py` | Mock/recorded adapters, capability rejection, malformed output, missing credentials |
| `test_redaction_and_cost.py` | Secret redaction and cost metadata |
| `test_resilience.py` | Timeout/retry normalization |
| `test_fixture_secrets.py` | Recorded fixtures contain no API key patterns |
| Contract cross-language fixtures | Python/TS parity for generation contracts |

## Commands executed and results

| Command | Result |
|---------|--------|
| `uv run ruff check .` | **PASS** |
| `uv run mypy apps services packages` | **KNOWN ISSUE** — pre-existing `apps/api/src/aegis_api/db/session.py` duplicate module path (Phase 16/17 precedent) |
| `uv run pytest -q` | **PASS** — 472 passed, 35 skipped |
| `uv run pytest tests/agents/provider-conformance -q` | **PASS** — 13 passed, 2 skipped |
| `uv run lint-imports` | **PASS** — 4 kept, 0 broken |
| `pnpm check-contracts` | **PASS** |
| `pnpm typecheck` | **PASS** |
| `pnpm lint` | **PASS** |
| `pnpm test` | **PASS** — 57 tests |
| `uv run python scripts/run_provider_harness.py` | **PASS** — mock, recorded, invalid output checks |
| `node apps/web/scripts/capture-provider-demo.mjs` | **PASS** — 10 screenshots captured |

## Architecture decisions and ADRs

- **Created:** [0019-model-provider-abstraction.md](../AEGIS-v1.0-Agent-Specs/adrs/0019-model-provider-abstraction.md) (Status: **Proposed**)
- No ADR changes beyond 0019; graph-risk remains ADR 0018

## Known limitations

- Streaming responses deferred
- Cost estimates are audit metadata only
- Hosted/local adapter live checks skipped in CI without credentials/endpoints
- `AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS` is for harness/demo when PostgreSQL is unavailable; production should use PostgreSQL persistence

## Deferred work

- Phase 19 agent runtime, roles, tool registry, grounding validation
- Agent session orchestration and approval workflows
- Three.js / reporting phases

## Risks for dependent phases

- Phase 19 must use `create_generation_service` / `AgentGenerationFacade`; no direct SDK imports
- Preserve mock/recorded providers as CI defaults
- Model output remains untrusted; never write directly to simulation authoritative tables

## Acceptance criteria evidence

1. **Agent code can switch providers without changes:** `ProviderRegistry.resolve()` + shared `GenerationRequestV1`; conformance tests run same request against mock and recorded providers
2. **Provider failures bounded and observable:** `resilience.py` timeout/retry/circuit breaker; normalized `ProviderErrorCode`; tests for timeout, `RETRY_EXHAUSTED`, `CREDENTIALS_MISSING`, `CAPABILITY_UNSUPPORTED`
3. **Fake/recorded providers support core CI:** Default `AEGIS_PROVIDER_DEFAULT=mock`; full pytest suite passes without external inference; hosted/local tests skipped without credentials
4. **Usage and artifacts auditable without secrets:** `GenerationArtifactV1` persistence, `redaction.py`, `test_fixture_secrets.py`, `test_redaction_and_cost.py`

## Prohibited-shortcut confirmation

No agent runtime, no direct SDK leakage into contracts, no unbounded retries, no provider calls bypassing `GenerationService`, no secrets in fixtures/logs, validation commands executed as recorded.
