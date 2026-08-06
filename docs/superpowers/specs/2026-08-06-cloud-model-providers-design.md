# Cloud model providers for the copilot — design

**Date:** 2026-08-06
**Status:** Approved (user delegated all decisions for this session; design derived from their written brief)
**Author:** Claude (orchestrator), from user brief + three codebase surveys

## Goal

Let a user pick the AI model provider for a run in the **Configure Loadout** dialog:

1. **Local model** — current setup (the `openai-compatible` adapter pointed at the local llama-server). Default.
2. **OpenAI** — user's own cloud subscription (API key).
3. **OpenRouter** — user's API key.
4. **Ollama Cloud** — user's API key.

For cloud providers the user enters their API key **once**; it is verified live against the provider, stored **encrypted, per user account**, and reused on later runs. After choosing a provider the user picks a **model** from that provider's live model list. The chosen provider + model are fixed for the run and drive every copilot/agent generation in that run.

## Non-goals

- No streaming (the provider layer has none today; unchanged).
- No per-agent-role provider pinning — one provider/model per run.
- No admin UI for other users' credentials.
- No billing/usage dashboards. Cost estimation may return unknown for new providers.
- Mock/recorded providers stay env-only (CI/dev), not shown in the loadout picker.

## Provider facts

| Provider | provider_id | Base URL | Auth |
|---|---|---|---|
| Local model | `openai-compatible` (existing) | `AEGIS_PROVIDER_LOCAL_BASE_URL` | none/env |
| OpenAI | `openai` (existing) | `https://api.openai.com/v1` | per-user key |
| OpenRouter | `openrouter` (new) | `https://openrouter.ai/api/v1` | per-user key |
| Ollama Cloud | `ollama-cloud` (new) | `https://ollama.com/v1` | per-user key |

All four speak the OpenAI chat-completions wire format, so the two new adapters subclass `OpenAIHostedProvider` exactly as `OpenAICompatibleProvider` does (~40 lines each). Both new base URLs are appended to the `AEGIS_PROVIDER_EGRESS_ALLOWLIST` default and `.env.example` — the egress gate stays fail-closed.

## Architecture

### 1. Credential storage (new)

- **Table** `auth_user_provider_credentials` (migration `020_provider_credentials.py`, modeled on `015_password_credentials.py`):
  - `user_id` FK → `auth_users.user_id`, `ondelete=CASCADE`
  - `provider` String(64) — one of the cloud provider ids
  - `ciphertext` — Fernet-encrypted API key (LargeBinary or Text)
  - `key_hint` String(8) — last 4 chars of the key, plaintext, for "Connected (…abcd)" UI
  - `algorithm` String(32) default `fernet`
  - `verified_at`, `created_at`, `updated_at` (timezone-aware)
  - PK/unique `(user_id, provider)`
- **ORM row** `AuthUserProviderCredentialRow` in `packages/persistence/.../orm/tables.py` beside the other `Auth*Row` classes; repository methods on `PostgresAuthRepository` (get/upsert/delete/list-status per user).
- **Crypto**: new module `apps/api/src/aegis_api/auth/provider_credentials.py` mirroring `passwords.py` style. Fernet from the `cryptography` package (new dependency of the api app). Key material from a new optional `AEGIS_CREDENTIAL_ENCRYPTION_KEY` field on `AegisSettings` (documented in `.env.example` with the one-liner to generate one; `scripts/bootstrap.sh` auto-generates and appends it to `.env` if missing). If unset, credential endpoints return a clear 503 config error; nothing else in the app is affected.
- Plaintext keys exist only: (a) in the PUT request body, (b) transiently in memory during verification/encryption/generation-client construction. Never in logs, contracts, run payloads, generation artifacts, or GET responses.

### 2. Credential + catalog API (new router `apps/api/src/aegis_api/provider_credentials/router.py`)

All routes `require_actor`; strictly self-scoped (actor's own user_id only — same no-leak discipline as `run_authz.py`).

- `GET /api/v1/provider-credentials` → `[{provider, configured, keyHint, verifiedAt}]` — status only, never key material.
- `PUT /api/v1/provider-credentials/{provider}` body `{apiKey}` → verifies the key by calling the provider's `GET {base}/models`; on success encrypts + upserts, returns the status object; on auth failure returns 400 with a classified message; on network failure 502. Verification goes through the model-provider package (egress allowlist applies), not ad-hoc HTTP.
- `DELETE /api/v1/provider-credentials/{provider}` → disconnect.
- `GET /api/v1/providers/{provider}/models` → live model list via the provider's `/models` endpoint using the caller's stored credential (local model: returns the configured local model). Normalized `[{id, label}]`, sorted. OpenAI results filtered to chat-capable models (drop embeddings/audio/image/moderation/realtime by id pattern). 400 if no credential stored for that provider.
- `GET /api/v1/providers/loadout-options` → the four selectable providers `[{id, label, requiresCredential}]` for the dialog (mock/recorded excluded).

Model listing lives in the model-provider package as a small `list_models()` on the OpenAI-SDK-based adapters (`client.models.list()`), so the router stays thin and the egress gate is enforced in one place.

### 3. Contracts (additive, schemaVersion stays 1)

- `RunLoadoutV1` / `runLoadoutSchema`: add optional `providerId: string | null` and `modelId: string | null` (default null = local/default behavior). Mirror Python/TS, regenerate JSON Schemas, `pnpm check-contracts`.
- New small contracts for credential status and model-list responses (Python + TS mirrors, versioned per convention).
- No secrets and no credential references in any contract.

### 4. Runtime wiring (per-run provider → every generation)

- Run creation (`RunCommandService.create_run`): if `loadout.providerId` is a cloud provider, validate the owner has a stored credential (400 otherwise) and that the provider id is known. Loadout persists on the run payload as today.
- Task creation paths (copilot chat via `apps/api/.../agents/router.py`, autonomy via `services/agents/.../autonomy/service.py`): when creating a task for a run whose loadout pins a provider, set `provider_id` (and new `model_id`) from the loadout instead of the global default. Fallback unchanged (`AEGIS_PROVIDER_DEFAULT`).
- Executor/generation: thread the real `model_id` into `build_definition`/`ModelConfigV1` (replacing the synthetic `f"{provider_id}-v1"` when a real model is pinned). For cloud providers, resolve + decrypt the **run owner's** credential and construct the adapter with that key via a registry override seam (e.g. `ProviderRegistry.resolve(...)` gains per-call overrides, or the agents' provider factory builds a per-call adapter). Constraints:
  - Decrypt **before** the LLM call and **outside any DB transaction** (the executor must never hold a txn across a provider call — existing invariant).
  - The key goes only into the SDK client construction, never into `GenerationRequestV1` or persisted artifacts (add a test asserting artifacts contain no key material).
  - Missing/revoked credential at generation time → classified auth error, task fails visibly (same as a bad env key today).
- Context window / output tokens: keep the global `AEGIS_PROVIDER_TIMEOUT_SECONDS` and `AEGIS_PROVIDER_MAX_OUTPUT_TOKENS` ceilings — cloud providers are faster than the local model, so existing budgets are safe.

### 5. Frontend (Configure Loadout)

New **"AI model provider"** section in `loadout-launch-dialog.tsx`, below Rules of Engagement, following the existing hand-rolled radio-card pattern:

- Four radio-cards: Local model (default) / OpenAI / OpenRouter / Ollama Cloud, each with one line of doctrine copy.
- Selecting a cloud provider with **no stored credential**: inline masked key input (`type="password"`, autocomplete off) + **Connect** button → PUT verify/save; spinner + classified error message on failure; success flips to connected state.
- **With stored credential**: "Connected (…abcd)" affordance + a model select populated from the live models endpoint (type-to-filter listbox — OpenRouter lists hundreds of models; filter-as-you-type keeps it clean). A small "Replace key" / "Disconnect" affordance.
- Launch is blocked (button disabled with hint) until a cloud selection has both a credential and a model picked. Local model needs nothing.
- Submit includes `providerId`/`modelId` in the loadout object (omitted for local).
- All fetches via `apiFetch` (cross-origin auth); TanStack Query hooks in a new `apps/web/features/loadout/use-provider-credentials.ts`.
- `DEFAULT_LOADOUT`, `useCreateRun`'s `CreateRunLoadout`, and `LoadoutChips` (new provider/model chip; never any key material) updated.
- Reduced-motion + a11y obligations as elsewhere (radiogroup semantics, labels, focus management).

## Error handling summary

| Failure | Surface |
|---|---|
| Encryption key env unset | 503 config error from credential endpoints; UI shows "server not configured for cloud providers" |
| Invalid API key on connect | 400 with provider-classified message, key not stored |
| Provider unreachable on connect/model-list | 502, key not stored / list empty with retry affordance |
| Run launched with cloud provider but no credential | 400 at `POST /runs` (UI prevents this anyway) |
| Credential deleted mid-run | Generation fails with classified auth error; task fails visibly |

## Testing

- Unit: crypto round-trip + tamper rejection; adapter construction/egress for the two new providers; model-list normalization/filtering; repo upsert/unique constraint.
- Contract: loadout additive fields Python↔TS parity (`pnpm check-contracts`); new credential/model contracts.
- API: credential routes (auth required, self-scoped, no plaintext in any response, verification mocked via provider fakes), models proxy, run-creation validation.
- Runtime: task creation picks up loadout provider/model; artifact contains no key material; deterministic provider fakes only — **core CI must pass with no external LLM**, per the architecture contract.
- Frontend: vitest for the new section's states (unconnected/connecting/connected/error), a11y via vitest-axe; e2e smoke optional.
- Manual: Chrome QA pass on the loadout dialog (visual verification is mandatory for UI changes).

## Rollout / compat

- All contract changes additive; existing runs (loadout without the new fields) behave exactly as today.
- `AEGIS_PROVIDER_DEFAULT` and env-key config keep working for admin/debug console paths (`POST /api/v1/providers/generate`) and as the fallback when no provider is pinned.
- No ADR needed: no new infra, no architecture-contract conflict; this extends the existing provider registry and auth schema along established seams.
