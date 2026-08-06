"""Provider configuration loaded from environment variables."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderKind(StrEnum):
    MOCK = "mock"
    RECORDED = "recorded"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    OPENROUTER = "openrouter"
    OLLAMA_CLOUD = "ollama-cloud"


#: Kinds that reach a third-party endpoint with a per-user subscription key. They are
#: selectable in the loadout dialog and require a stored credential; the local and
#: fixture-serving kinds do not.
CLOUD_PROVIDER_KINDS: frozenset[ProviderKind] = frozenset(
    {ProviderKind.OPENAI, ProviderKind.OPENROUTER, ProviderKind.OLLAMA_CLOUD}
)


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    AEGIS_PROVIDER_DEFAULT: ProviderKind = ProviderKind.MOCK
    # Ceiling on ONE attempt. A local reasoning model at ~25 tok/s spends minutes
    # on a long prompt, so the bound is hours-capable rather than the old 600s.
    # The *total* budget for a call (every attempt plus backoff) is the caller's
    # ``timeout_ms``, which is what actually bounds operator-facing latency.
    AEGIS_PROVIDER_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=3600)
    AEGIS_PROVIDER_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    AEGIS_PROVIDER_RETRY_BACKOFF_SECONDS: float = Field(default=1.0, ge=0.1, le=60.0)
    # Backoff used instead of the exponential one when the endpoint reports it is
    # still loading its weights. llama-server lazy-loads a multi-GB GGUF on the
    # first request and 503s meanwhile; 1s/2s/4s burns every retry inside seven
    # seconds of a load that takes minutes.
    AEGIS_PROVIDER_COLD_START_BACKOFF_SECONDS: float = Field(default=15.0, ge=0.1, le=300.0)
    # (The admin reachability probe's budget is AEGIS_PROVIDER_PROBE_TIMEOUT_MS,
    # owned by health_probe.py — deliberately independent of the generation
    # timeout, since an admin page must not hang on a wedged model server.)
    AEGIS_PROVIDER_CIRCUIT_BREAKER_THRESHOLD: int = Field(default=5, ge=1, le=100)
    AEGIS_PROVIDER_CIRCUIT_BREAKER_RESET_SECONDS: int = Field(default=60, ge=1, le=3600)
    AEGIS_PROVIDER_MAX_CONCURRENT_REQUESTS: int = Field(default=10, ge=1, le=256)
    AEGIS_PROVIDER_MAX_OUTPUT_TOKENS: int = Field(default=4096, ge=1, le=65536)
    AEGIS_PROVIDER_MAX_COST_USD: float | None = Field(default=None, ge=0.0)
    AEGIS_PROVIDER_RECORDED_FIXTURES_DIR: str = "fixtures/model-responses"

    AEGIS_PROVIDER_OPENAI_API_KEY: str = ""
    AEGIS_PROVIDER_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AEGIS_PROVIDER_OPENAI_MODEL: str = "gpt-4o-mini"

    # llama.cpp llama-server (host binary) exposes an OpenAI-compatible API. The
    # supported default local path is the host-served server on :8086. Run it with:
    #   llama-server -m <model.gguf> --host 127.0.0.1 --port 8086 -c 262144 -ngl 99 -fa on
    # It serves /v1/chat/completions, /v1/completions, and /v1/models on :8086/v1.
    # (From inside a container reach the host binary at host.docker.internal:8086.)
    AEGIS_PROVIDER_LOCAL_BASE_URL: str = "http://localhost:8086/v1"
    # llama-server ignores the API key unless started with --api-key; the OpenAI
    # SDK still requires a non-empty value, so this is a harmless placeholder.
    AEGIS_PROVIDER_LOCAL_API_KEY: str = "llama-cpp"
    # Must match the model id llama-server reports at /v1/models (its --alias or
    # the loaded GGUF basename). Requests may override this per model config.
    AEGIS_PROVIDER_LOCAL_MODEL: str = "local-model"
    # OpenRouter and Ollama Cloud speak the same OpenAI chat-completions wire format.
    # Their keys and models normally arrive per call, from the run owner's stored
    # credential and the run's loadout; the env vars are the admin/debug fallback and
    # stay unset (None) in a per-user deployment.
    AEGIS_PROVIDER_OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AEGIS_PROVIDER_OPENROUTER_API_KEY: str | None = None
    AEGIS_PROVIDER_OPENROUTER_MODEL: str | None = None
    AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL: str = "https://ollama.com/v1"
    AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY: str | None = None
    AEGIS_PROVIDER_OLLAMA_CLOUD_MODEL: str | None = None

    AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS: bool = False
    AEGIS_PROVIDER_EGRESS_ALLOWLIST: str = (
        "https://api.openai.com/v1,http://localhost:8086/v1,"
        "https://openrouter.ai/api/v1,https://ollama.com/v1"
    )

    @property
    def timeout_ms(self) -> int:
        return self.AEGIS_PROVIDER_TIMEOUT_SECONDS * 1000

    @property
    def recorded_fixtures_path(self) -> Path:
        return Path(self.AEGIS_PROVIDER_RECORDED_FIXTURES_DIR)

    @property
    def provider_egress_allowlist(self) -> list[str]:
        return [
            value.strip()
            for value in self.AEGIS_PROVIDER_EGRESS_ALLOWLIST.split(",")
            if value.strip()
        ]


def load_provider_settings() -> ProviderSettings:
    return ProviderSettings()
