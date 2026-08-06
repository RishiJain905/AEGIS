# Cloud Model Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pick Local / OpenAI / OpenRouter / Ollama Cloud (+ model) per run in Configure Loadout, with per-user encrypted API keys verified live and reused across runs.

**Architecture:** Two new ~40-line OpenAI-compatible adapters plug into the existing `ProviderRegistry`; a new `auth_user_provider_credentials` table stores Fernet-encrypted keys; the loadout contract gains additive `providerId`/`modelId`; task-creation paths thread the run's choice (and the owner's decrypted key, outside any DB txn) into the existing per-request provider resolution.

**Tech Stack:** SQLAlchemy 2 async + Alembic, FastAPI, Pydantic/Zod mirrored contracts, `cryptography` (Fernet, new dep), Next.js 15 + TanStack Query, existing `openai` SDK adapters.

**Spec:** `docs/superpowers/specs/2026-08-06-cloud-model-providers-design.md` — read it first; it is binding.

## Global Constraints

- Base URLs: OpenAI `https://api.openai.com/v1`, OpenRouter `https://openrouter.ai/api/v1`, Ollama Cloud `https://ollama.com/v1`. Both new URLs must be added to the `AEGIS_PROVIDER_EGRESS_ALLOWLIST` default and `.env.example`.
- Provider ids (wire-stable strings): `openai-compatible` (local), `openai`, `openrouter`, `ollama-cloud`.
- Plaintext API keys may exist ONLY in: PUT request body, transient memory during verify/encrypt/client construction. Never in logs, contracts, run payloads, generation artifacts, or any GET response. `key_hint` (last 4 chars) is the only persisted plaintext derivative.
- All contract changes are additive; `schemaVersion` stays 1. After contract edits: `uv run python scripts/generate_contract_schemas.py` (it rewrites ~190 schemas then dies on a pnpm spawn — that's known; re-run Prettier after) then `pnpm check-contracts`.
- Core CI must pass with no external LLM — all tests use deterministic fakes/mocks.
- Never hold a DB transaction across a provider/LLM call.
- pnpm only (never npm/npx); Python via `uv run`. Bash scripts via Git Bash on this machine.
- Commit per task with `git commit --only <paths>` (shared branch; other sessions may commit concurrently).
- Gate for "done" on every task: `pnpm typecheck`, `pnpm lint`, `uv run ruff check .`, `pnpm typecheck:py`, plus the task's own tests. Full `scripts/verify.ps1` runs once at the end of the whole plan.

---

### Task 1: Provider package + contracts foundation

**Files:**
- Modify: `packages/model-provider/src/aegis_model_provider/config.py` (ProviderKind enum, new settings fields, egress default)
- Create: `packages/model-provider/src/aegis_model_provider/adapters/openrouter.py`
- Create: `packages/model-provider/src/aegis_model_provider/adapters/ollama_cloud.py`
- Modify: `packages/model-provider/src/aegis_model_provider/adapters/openai_hosted.py` (add `api_key_override`/`model_id_override` ctor params + `list_models()`)
- Modify: `packages/model-provider/src/aegis_model_provider/registry.py` (`build_provider_registry` + new `resolve_with_credentials`)
- Modify: `packages/contracts-python/src/aegis_contracts/entities.py` (RunLoadoutV1) and new `provider_credentials.py` contract module; mirror in `packages/contracts-ts/src/entities.ts` + new `provider-credentials.ts`; version registry entries in `versioning.ts`/Python equivalent
- Modify: `.env.example`
- Test: `packages/model-provider/tests/` (follow existing test layout), `tests/contract/`

**Interfaces (Produces — later tasks rely on these exact names):**
- `ProviderKind.OPENROUTER = "openrouter"`, `ProviderKind.OLLAMA_CLOUD = "ollama-cloud"`
- `OpenAIHostedProvider.__init__(..., api_key_override: str | None = None, model_id_override: str | None = None)` — override wins over env settings in `_client()` / `_resolve_model_id()`
- `async OpenAIHostedProvider.list_models(self) -> list[str]` — via `client.models.list()`; subclasses inherit
- `ProviderRegistry.resolve_with_credentials(self, provider_id: str, *, api_key: str | None = None, model_id: str | None = None) -> ModelProvider` — fresh adapter instance of the same kind with overrides; raises the same VALIDATION_FAILED as `resolve` for unknown ids; local (`openai-compatible`) accepts `api_key=None`
- Contracts (Python names / TS camelCase mirrors):
  - `RunLoadoutV1.provider_id: str | None = Field(default=None, alias="providerId")`, `RunLoadoutV1.model_id: str | None = Field(default=None, alias="modelId")` (additive, optional, no version bump)
  - `ProviderCredentialStatusV1 { schema_version, provider: str, configured: bool, key_hint: str | None, verified_at: datetime | None }`
  - `ProviderModelEntryV1 { id: str, label: str }`, `ProviderModelListV1 { schema_version, provider: str, models: list[ProviderModelEntryV1] }`
  - `LoadoutProviderOptionV1 { id: str, label: str, requires_credential: bool }`

**Steps:**

- [ ] Write failing tests: adapter construction for both new kinds asserts `provider_id`, egress-allowlist enforcement (URL absent from allowlist → VALIDATION_FAILED at construction), `api_key_override` reaches the SDK client, `resolve_with_credentials` returns a distinct instance and rejects unknown ids, `list_models` normalizes a mocked `models.list()` response.
- [ ] Run them, confirm failure for the right reason.
- [ ] Implement `config.py` changes: enum members; `AEGIS_PROVIDER_OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`), `AEGIS_PROVIDER_OPENROUTER_API_KEY: str | None`, `AEGIS_PROVIDER_OPENROUTER_MODEL: str | None`, same trio for `OLLAMA_CLOUD` (base default `https://ollama.com/v1`); append both bases to the egress allowlist default.
- [ ] Implement the two adapters as subclasses mirroring `adapters/openai_compatible.py` (~40 lines each: `provider_id`, `__init__` base-url wiring, `_client()` key selection honoring `api_key_override`).
- [ ] Implement `list_models()` + override params on `openai_hosted.py`; `registry.py` additions (`build_provider_registry` instantiates both; `resolve_with_credentials` re-constructs by kind with overrides).
- [ ] Contracts, both languages, additive; run schema generation + Prettier + `pnpm check-contracts`.
- [ ] `.env.example`: new vars + allowlist line, following the existing `AEGIS_PROVIDER_*` block style.
- [ ] All tests + typechecks + lints pass. Commit (`--only` the touched paths).

### Task 2: Encrypted per-user credentials — storage + API

**Files:**
- Create: `packages/persistence/src/aegis_persistence/credentials.py` (Fernet encrypt/decrypt helpers)
- Modify: `packages/persistence/src/aegis_persistence/orm/tables.py` (`AuthUserProviderCredentialRow`)
- Create: `packages/persistence/src/aegis_persistence/repositories/provider_credentials.py` (`PostgresProviderCredentialRepository`)
- Modify: `packages/persistence/src/aegis_persistence/unit_of_work.py` (`uow.provider_credentials` property)
- Create: `migrations/versions/020_provider_credentials.py` (model on `015_password_credentials.py`; `revision = "020_provider_credentials"`, `down_revision = "019_run_created_at"`)
- Modify: `packages/contracts-python/src/aegis_contracts/settings.py` (`AEGIS_CREDENTIAL_ENCRYPTION_KEY: str | None = None`)
- Modify: `packages/persistence/pyproject.toml` (add `cryptography`), then `uv sync`
- Create: `apps/api/src/aegis_api/provider_credentials/router.py` (+ register in the app factory beside existing routers)
- Modify: `apps/api/src/aegis_api/providers/router.py` (`GET /api/v1/providers/loadout-options`)
- Modify: `.env.example`, `scripts/bootstrap.sh` (generate+append key if missing)
- Test: `tests/unit/` (crypto, repo with in-memory/session fixtures per existing patterns), API tests beside existing router tests

**Interfaces:**
- Consumes (Task 1): `ProviderRegistry.resolve_with_credentials`, `list_models()`, contract types, provider id strings.
- Produces:
  - `encrypt_api_key(plaintext: str, *, key: str) -> bytes` / `decrypt_api_key(ciphertext: bytes, *, key: str) -> str` (raises `CredentialDecryptError` on tamper/wrong key)
  - Table `auth_user_provider_credentials(user_id FK CASCADE, provider String(64), ciphertext LargeBinary, key_hint String(8), algorithm String(32) default 'fernet', verified_at, created_at, updated_at, PRIMARY KEY (user_id, provider))`
  - Repo: `async get(user_id, provider) -> Row | None`, `async upsert(user_id, provider, ciphertext, key_hint, verified_at)`, `async delete(user_id, provider) -> bool`, `async list_status(user_id) -> list[Row]`, and the one Task 3 needs: `async get_decrypted_api_key(user_id: str, provider: str, *, encryption_key: str) -> str | None`
  - Routes (all `require_actor`, self-scoped): `GET /api/v1/provider-credentials` → `list[ProviderCredentialStatusV1]`; `PUT /api/v1/provider-credentials/{provider}` body `{"apiKey": "..."}` → verify via `resolve_with_credentials(provider, api_key=key).list_models()` then encrypt+upsert → `ProviderCredentialStatusV1` (400 invalid key / 502 unreachable / 503 if `AEGIS_CREDENTIAL_ENCRYPTION_KEY` unset / 404 unknown-or-local provider); `DELETE /api/v1/provider-credentials/{provider}` → 204; `GET /api/v1/providers/{provider}/models` → `ProviderModelListV1` using the caller's stored key (local returns configured local model; 400 if no credential); `GET /api/v1/providers/loadout-options` → the 4 options, `requiresCredential` false only for `openai-compatible`.

**Steps:**

- [ ] Failing tests first: crypto round-trip + tamper rejection; repo upsert-overwrites + composite-key uniqueness; router tests with a faked registry (verify 400/502/503/404 branches, assert NO response body ever contains the plaintext key, assert non-owner cannot see another user's rows).
- [ ] Implement crypto module, ORM row, repo, UoW property, migration (upgrade AND downgrade; verify `uv run alembic upgrade head` against local postgres).
- [ ] Implement routers; provider verification errors mapped via the existing provider error classification.
- [ ] Settings field + `.env.example` (with the Fernet keygen one-liner in a comment) + `bootstrap.sh` auto-generation.
- [ ] Tests + typechecks + lints pass. Commit.

### Task 3: Runtime wiring — loadout → tasks → generation

**Files:**
- Modify: `services/simulation/src/aegis_simulation/run_command_service.py` (`create_run` validation)
- Modify: `apps/api/src/aegis_api/agents/router.py` (copilot task creation reads run loadout)
- Modify: `services/agents/src/aegis_agents/autonomy/service.py` + `runtime/task_service.py` (autonomy task creation reads run loadout)
- Modify: `services/agents/src/aegis_agents/runtime/registry.py` (`build_definition(role, provider_id, model_id=None)` — real model id replaces synthetic `f"{provider_id}-v1"` when given)
- Modify: `services/agents/src/aegis_agents/runtime/executor.py` + `providers/factory.py` (per-call credential resolve/decrypt → `resolve_with_credentials`)
- Test: `tests/agents/`, `tests/unit/`

**Interfaces:**
- Consumes: Task 1's contract fields (`run.loadout.provider_id/model_id`) and `resolve_with_credentials`; Task 2's `get_decrypted_api_key` + `AEGIS_CREDENTIAL_ENCRYPTION_KEY` setting.
- Produces: agent tasks whose `provider_id`/model config come from the run loadout when set; unchanged global-default behavior when unset.

**Steps:**

- [ ] Failing tests: `create_run` with cloud `providerId` + no stored credential → validation error (400 at API level); with credential → run persists loadout verbatim. Task creation for a loadout-pinned run carries `provider_id`/`model_id` from loadout; unpinned run keeps `AEGIS_PROVIDER_DEFAULT`. Executor test with fake provider + fake credential repo: decrypted key is fetched before generation and OUTSIDE any transaction (assert via session/txn spy or by construction), and the persisted `GenerationArtifactV1` contains no key material (string-search the serialized artifact for the fake key).
- [ ] Implement run-creation validation (unknown provider id → 400; cloud provider without owner credential → 400 with actionable message).
- [ ] Implement task-creation threading in both call paths (copilot router + autonomy) and `build_definition` model-id support.
- [ ] Implement executor/factory credential injection: resolve owner user_id from the run, decrypt via Task 2 helper, `resolve_with_credentials(provider_id, api_key=key, model_id=model_id)`; missing/revoked credential → classified auth error, task fails visibly.
- [ ] Tests + typechecks + lints pass. Commit.

### Task 4: Frontend — loadout dialog provider section

**Files:**
- Modify: `apps/web/features/loadout/loadout-launch-dialog.tsx` (new "AI model provider" section below RoE)
- Create: `apps/web/features/loadout/use-provider-credentials.ts` (TanStack Query hooks over `apiFetch`)
- Modify: `apps/web/features/command-surface/contracts.ts` (`DEFAULT_LOADOUT` + provider option labels/doctrine copy)
- Modify: `apps/web/features/live-run/use-run-commands.ts` (`CreateRunLoadout` + submit body)
- Modify: `apps/web/features/loadout/loadout-chips.tsx` (provider/model chip; never key material)
- Test: colocated vitest + vitest-axe

**Interfaces:**
- Consumes (Task 2 endpoints): `GET /api/v1/providers/loadout-options`, `GET /api/v1/provider-credentials`, `PUT/DELETE /api/v1/provider-credentials/{provider}`, `GET /api/v1/providers/{provider}/models`. All via `apiFetch` (raw fetch 401s cross-origin). Non-GET requests need the CSRF header — follow whatever `useCreateRun` already does.
- Produces: loadout submit object gains `providerId`/`modelId` (omitted entirely for local, matching the omit-not-null convention in `useCreateRun`).

**Steps:**

- [ ] Failing component tests: section renders 4 radio-cards defaulting to Local; selecting a cloud provider without credential shows masked key input + Connect; connected state shows "Connected (…abcd)", model select (type-to-filter listbox — OpenRouter returns hundreds of models), and Replace/Disconnect; Launch disabled until credential+model present for cloud selection; submit payload contains `providerId`/`modelId` only for cloud; axe passes on every state.
- [ ] Implement hooks (`useLoadoutProviderOptions`, `useProviderCredentials`, `useConnectProviderCredential`, `useProviderModels`) with query invalidation on connect/disconnect.
- [ ] Implement the dialog section imitating the existing RoE radio-card pattern (fieldset/radiogroup semantics, same visual language — this is a stylized dark command-center UI; match it, don't import a generic component kit). Key input: `type="password"`, `autoComplete="off"`, never echoed after save.
- [ ] Update `DEFAULT_LOADOUT`, `CreateRunLoadout`, chips.
- [ ] Tests + `pnpm --filter @aegis/web test` + typecheck + lint pass. Commit.

### Task 5: End-to-end verification (orchestrator)

- [ ] Full gate: `scripts/verify.ps1` → `VERIFY: PASS` (integration suites need postgres+redis; remember the isolated-DB rule for `-Integration`).
- [ ] Rebuild the Docker web/api images, then Chrome QA subagent pass on `localhost:3000`: open Configure Loadout, verify the 4 options render, local flow unchanged, cloud flow shows key entry (enter a dummy key → expect a clean 400 "invalid key" surface, NOT a crash), connected-state UI if any real key is available, launch-blocked states correct. Screenshots in the report.
- [ ] Update `.env` locally with a generated `AEGIS_CREDENTIAL_ENCRYPTION_KEY` + run `uv run alembic upgrade head`.

## Self-review notes

- Spec coverage: storage/API/contracts/runtime/frontend/error-table/testing all map to Tasks 1–4; rollout/compat is inherent (additive fields, default fallbacks). Cost-table extension explicitly skipped per spec non-goals.
- Type consistency: `resolve_with_credentials`, `get_decrypted_api_key`, contract names, and endpoint paths are quoted identically in producing and consuming tasks.
- Execution: subagent-driven; Tasks 1→2→3 sequential (hard interface deps); Task 4 may run in parallel with Task 3 after Task 2 lands (disjoint files; `git commit --only` discipline).
