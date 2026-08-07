"""Hosted reasoning models must be left room to actually answer.

Chrome QA drove run ``run_HAQWCJAZ9P7CVFZVKMNEH9WXQ5`` on OpenRouter
(``deepseek/deepseek-v4-flash-0731``). Every TRACE turn died with

    PROVIDER_FAILURE: Provider spent its entire output budget on reasoning and
    returned no content; raise the output token budget

The diagnosis was right and the budget was wrong. ``max_tokens`` on the OpenAI wire
bounds *reasoning plus answer* in one pool, so a 4096-token pool is a pool the model
may spend entirely on thinking, leaving nothing for the content the schema needs.

Two levers fix that, and the cloud adapters use both:

* a larger pool (``AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS``), and
* a cap on the thinking itself (``AEGIS_PROVIDER_REASONING_EFFORT``), which is what
  keeps the larger pool from becoming a longer wall clock. That matters because the
  measured route produced its 4096 tokens in roughly the whole 60s per-attempt
  ceiling: without capping the scratchpad, a bigger pool would just convert an honest
  OUTPUT_LIMIT_EXCEEDED into a TIMEOUT.

The local llama-server path is deliberately excluded from both — its requests must go
out byte-identical, since it is the slow path whose latency the chain is tuned around.

Nothing here touches the network: the SDK client is faked.
"""

from __future__ import annotations

from typing import Any

import pytest
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderErrorCode,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider.adapters.ollama_cloud import OllamaCloudProvider
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.adapters.openrouter import OpenRouterProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
LOCAL_BASE_URL = "http://localhost:8086/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"
ALL_BASE_URLS = ",".join(
    [OPENAI_BASE_URL, LOCAL_BASE_URL, OPENROUTER_BASE_URL, OLLAMA_CLOUD_BASE_URL]
)

_PAYLOAD = '{"summary": "identity broker compromised", "confidence": 0.7}'


def settings(**overrides: Any) -> ProviderSettings:
    return ProviderSettings(
        _env_file=None,
        AEGIS_PROVIDER_EGRESS_ALLOWLIST=ALL_BASE_URLS,
        AEGIS_PROVIDER_OPENROUTER_API_KEY="or-key",
        AEGIS_PROVIDER_OPENROUTER_MODEL="deepseek/deepseek-v4-flash-0731",
        AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY="ol-key",
        AEGIS_PROVIDER_OLLAMA_CLOUD_MODEL="deepseek-v4-flash:0731-cloud",
        AEGIS_PROVIDER_OPENAI_API_KEY="oa-key",
        AEGIS_PROVIDER_LOCAL_MODEL="local-reasoner.gguf",
        **overrides,
    )


def request_for(provider_id: str) -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id=provider_id,
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id=provider_id,
            model_id=f"{provider_id}-v1",
            prompt_version="phase20-trace-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="You are TRACE."),
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Investigate."),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["summary", "confidence"],
                "additionalProperties": False,
            },
            strict=True,
            max_repair_attempts=0,
        ),
    )


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.role = "assistant"
        self.content = content
        self.model_extra: dict[str, Any] = {}


class _FakeUsage:
    prompt_tokens = 12
    completion_tokens = 34
    total_tokens = 46


class _FakeChoice:
    def __init__(self, content: str | None, finish_reason: str) -> None:
        self.message = _FakeMessage(content)
        self.finish_reason = finish_reason


class _FakeCompletion:
    def __init__(self, content: str | None, finish_reason: str) -> None:
        self.choices = [_FakeChoice(content, finish_reason)]
        self.usage = _FakeUsage()


class _RecordingCompletions:
    """Captures every request body, and optionally fails the first N of them."""

    def __init__(
        self,
        *,
        content: str | None = _PAYLOAD,
        finish_reason: str = "stop",
        failures: list[Exception] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._content = content
        self._finish_reason = finish_reason
        self._failures = list(failures or [])

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._failures:
            raise self._failures.pop(0)
        return _FakeCompletion(self._content, self._finish_reason)


class _FakeClient:
    def __init__(self, completions: _RecordingCompletions) -> None:
        self.chat = type("_Chat", (), {"completions": completions})()


def bind(provider: Any, completions: _RecordingCompletions) -> Any:
    client = _FakeClient(completions)
    provider._client = lambda: client  # type: ignore[method-assign]
    return provider


class _BadRequest(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 400
        self._message = message

    def __str__(self) -> str:
        return self._message


# --- the pool the wire actually gets -----------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "provider_id"),
    [(OpenRouterProvider, "openrouter"), (OllamaCloudProvider, "ollama-cloud")],
)
async def test_cloud_routes_get_the_larger_completion_pool(
    factory: Any, provider_id: str
) -> None:
    """The QA failure: 4096 was a pool the scratchpad could drink dry on its own."""
    completions = _RecordingCompletions()
    provider = bind(factory(settings(AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS=8192)), completions)

    await provider.generate(request_for(provider_id))

    assert completions.calls[0]["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_the_local_path_keeps_the_budget_it_was_tuned_with() -> None:
    """llama-server is the slow path the timeout chain is measured against."""
    completions = _RecordingCompletions()
    provider = bind(
        OpenAICompatibleProvider(
            settings(
                AEGIS_PROVIDER_MAX_OUTPUT_TOKENS=4096,
                AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS=8192,
            )
        ),
        completions,
    )

    await provider.generate(request_for("openai-compatible"))

    assert completions.calls[0]["max_tokens"] == 4096
    assert "reasoning_effort" not in completions.calls[0]


@pytest.mark.asyncio
async def test_the_openai_adapter_is_left_alone() -> None:
    """Its default model is not a reasoning model, and OpenAI 400s the parameter."""
    completions = _RecordingCompletions()
    provider = bind(
        OpenAIHostedProvider(settings(AEGIS_PROVIDER_MAX_OUTPUT_TOKENS=4096)), completions
    )

    await provider.generate(request_for("openai"))

    assert completions.calls[0]["max_tokens"] == 4096
    assert "reasoning_effort" not in completions.calls[0]


@pytest.mark.asyncio
async def test_a_caller_asking_for_more_than_the_cloud_default_still_wins() -> None:
    """The cloud pool is a floor for reasoning headroom, never a downgrade."""
    completions = _RecordingCompletions()
    provider = bind(
        OpenRouterProvider(
            settings(
                AEGIS_PROVIDER_MAX_OUTPUT_TOKENS=16384,
                AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS=8192,
            )
        ),
        completions,
    )
    request = request_for("openrouter").model_copy(update={"max_output_tokens": 12000})

    await provider.generate(request)

    assert completions.calls[0]["max_tokens"] == 12000


@pytest.mark.asyncio
async def test_the_exhausted_budget_error_reports_the_pool_that_was_actually_sent() -> None:
    """"Raise the output token budget" is only actionable if the number is real."""
    completions = _RecordingCompletions(content="", finish_reason="length")
    provider = bind(
        OpenRouterProvider(settings(AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS=8192)), completions
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(request_for("openrouter"))

    error = exc_info.value.error
    assert error.code is ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED
    assert error.details.get("maxOutputTokens") == 8192


# --- capping the scratchpad ---------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "provider_id"),
    [(OpenRouterProvider, "openrouter"), (OllamaCloudProvider, "ollama-cloud")],
)
async def test_cloud_routes_cap_how_long_the_model_may_think(
    factory: Any, provider_id: str
) -> None:
    completions = _RecordingCompletions()
    provider = bind(factory(settings(AEGIS_PROVIDER_REASONING_EFFORT="low")), completions)

    await provider.generate(request_for(provider_id))

    assert completions.calls[0]["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_an_empty_effort_setting_sends_no_reasoning_field_at_all() -> None:
    """The escape hatch for an endpoint that dislikes the parameter."""
    completions = _RecordingCompletions()
    provider = bind(OpenRouterProvider(settings(AEGIS_PROVIDER_REASONING_EFFORT="")), completions)

    await provider.generate(request_for("openrouter"))

    assert "reasoning_effort" not in completions.calls[0]


@pytest.mark.asyncio
async def test_an_endpoint_that_rejects_the_parameter_is_retried_without_it() -> None:
    """A model behind the router that has no scratchpad must still answer.

    Both vendors front hundreds of models; a 400 naming the parameter would
    otherwise turn a working route into a total outage for that model.
    """
    completions = _RecordingCompletions(
        failures=[_BadRequest("Error code: 400 - unsupported parameter: 'reasoning_effort'")]
    )
    provider = bind(
        OpenRouterProvider(settings(AEGIS_PROVIDER_REASONING_EFFORT="low")), completions
    )

    response = await provider.generate(request_for("openrouter"))

    assert response.structured_data == {"summary": "identity broker compromised", "confidence": 0.7}
    assert len(completions.calls) == 2
    assert "reasoning_effort" in completions.calls[0]
    assert "reasoning_effort" not in completions.calls[1]


@pytest.mark.asyncio
async def test_a_bad_request_about_anything_else_is_not_retried() -> None:
    """The fallback is narrow on purpose: it must not paper over a real 400."""
    completions = _RecordingCompletions(
        failures=[_BadRequest("Error code: 400 - context length exceeded")]
    )
    provider = bind(
        OpenRouterProvider(settings(AEGIS_PROVIDER_REASONING_EFFORT="low")), completions
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(request_for("openrouter"))

    assert exc_info.value.error.code is ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert len(completions.calls) == 1


# --- the budget chain stays orderable ----------------------------------------


def test_the_shipped_defaults_keep_the_larger_pool_bounded_in_time() -> None:
    """Tokens are seconds, so the two settings only make sense together.

    Measured on the QA route, 4096 completion tokens took most of the 60s
    per-attempt ceiling. A bigger pool with an uncapped scratchpad therefore does
    not buy an answer — it buys a timeout, which is a strictly worse diagnosis than
    the OUTPUT_LIMIT_EXCEEDED it replaces. The cap is what keeps a normal turn far
    below the pool, so the extra tokens are spent on a long *answer* rather than on
    more thinking. Shipping one without the other is the mistake this pins.
    """
    shipped = ProviderSettings(_env_file=None)

    assert (
        shipped.AEGIS_PROVIDER_CLOUD_MAX_OUTPUT_TOKENS > shipped.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS
    )
    assert shipped.AEGIS_PROVIDER_REASONING_EFFORT in {"minimal", "low"}
    # And the per-attempt ceiling still resolves inside the agent task deadline
    # (AEGIS_AGENT_TASK_TIMEOUT_SECONDS=120, less the runtime's 2s headroom).
    assert shipped.AEGIS_PROVIDER_TIMEOUT_SECONDS <= 118
