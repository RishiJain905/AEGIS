# Model Provider Setup

AEGIS routes model access through the provider abstraction. Provider output is
untrusted, validated structured data and an unavailable provider must not mutate the
simulation directly.

## Supported modes

| Mode | Use | Credentials/network | v1.0 behavior |
| --- | --- | --- | --- |
| `mock` | Deterministic local development, demo, and CI | None | Default; deterministic structured responses |
| `recorded` | Replay fixtures from `fixtures/model-responses/` | None | Deterministic fixture responses |
| `openai` | Optional hosted provider | API key and network | Graceful degradation on missing credentials or unavailable service |
| `openai-compatible` | Optional local llama.cpp `llama-server` (OpenAI-compatible) endpoint | Local endpoint configuration | Graceful degradation when the endpoint is unavailable |

The mock and recorded modes are the supported offline paths. Live and local modes are
optional integrations; they are not required for the release validation gate.

## Configuration

Copy `.env.example` to `.env` and inspect variables prefixed with `AEGIS_PROVIDER_`.
Keep `AEGIS_PROVIDER_DEFAULT=mock` for local verification and the deterministic demo.
Set a live or local provider explicitly only when its endpoint, credentials, model, and
capabilities have been verified. Never commit credentials or put them in a scenario
package.

### Local llama.cpp (`openai-compatible`)

The local mode targets llama.cpp's `llama-server`, which exposes an OpenAI-compatible
API (`/v1/chat/completions`, `/v1/completions`, `/v1/models`). **The supported default
local path is the `llama-server` host binary on port 8086** — you supply your own GGUF
model and run the server yourself. On the reference setup this is the AMD ROCm build
(`build-rdna3-gfx1101\bin\llama-server.exe`) serving a Qwen3.5-9B GGUF:

```bash
llama-server -m <model.gguf> --host 127.0.0.1 --port 8086 -c 262144 -ngl 99 -fa on --alias local-model
```

Then set `AEGIS_PROVIDER_DEFAULT=openai-compatible`. The base URL
(`AEGIS_PROVIDER_LOCAL_BASE_URL`, default `http://localhost:8086/v1`) must appear
verbatim in `AEGIS_PROVIDER_EGRESS_ALLOWLIST`; the egress guard fails closed on any
destination not in the allowlist. `AEGIS_PROVIDER_LOCAL_MODEL` must match the id
`llama-server` reports at `/v1/models` (its `--alias` or the loaded GGUF basename).
Live inference against this endpoint is user-verified: AEGIS does not ship the GGUF and
core CI never contacts it (agent tests use deterministic provider fakes).

When AEGIS itself runs in containers, reach the host binary at
`http://host.docker.internal:8086/v1`. A containerized `llama-server` is also available
as an **optional** alternative behind the `llama` profile
(`docker compose --profile llama up llama`, serving `:8086`); to use it, override
`AEGIS_PROVIDER_LOCAL_BASE_URL`/`AEGIS_PROVIDER_EGRESS_ALLOWLIST` to `http://llama:8086/v1`.
The core stack stays fully offline (default `mock`) when neither is configured.

## Validate a provider

```powershell
uv run python scripts/run_provider_harness.py
uv run pytest tests/agents/provider-conformance -q
```

All adapters implement the canonical `GenerationService.generate` path. Vendor SDK
types stay inside `aegis_model_provider.adapters.*`; agent roles consume the provider
interface, not a vendor SDK.

## No-model graceful degradation

When a live or local provider is unavailable, the service returns a normalized provider
error such as `CREDENTIALS_MISSING`, `TIMEOUT`, `RETRY_EXHAUSTED`, `CIRCUIT_OPEN`, or
`CAPABILITY_UNSUPPORTED`. The operator can inspect the failure and continue with
non-model portions of a simulation where the workflow permits it. A failed provider
request is not approval, is not a simulation mutation, and must remain observable in
the generation artifact/audit path.

## References

- [Provider contracts](../AEGIS-v1.0-Agent-Specs/agent-system/18-model-provider-abstraction.md)
- [Provider implementation](../../packages/model-provider/src/aegis_model_provider/)
- [Provider conformance tests](../../tests/agents/provider-conformance/)
