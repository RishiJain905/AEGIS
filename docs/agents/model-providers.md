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
| `openai-compatible` | Optional local Ollama/vLLM-style endpoint | Local endpoint configuration | Graceful degradation when the endpoint is unavailable |

The mock and recorded modes are the supported offline paths. Live and local modes are
optional integrations; they are not required for the release validation gate.

## Configuration

Copy `.env.example` to `.env` and inspect variables prefixed with `AEGIS_PROVIDER_`.
Keep `AEGIS_PROVIDER_DEFAULT=mock` for local verification and the deterministic demo.
Set a live or local provider explicitly only when its endpoint, credentials, model, and
capabilities have been verified. Never commit credentials or put them in a scenario
package.

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
