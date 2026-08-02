"""Local reasoning-model behaviour at the OpenAI-compatible adapter boundary.

The supported local endpoint is llama-server hosting a *reasoning* model. Three
of its behaviours broke the live pipeline and are pinned here:

* the answer can arrive in ``reasoning_content`` with ``content`` empty;
* a too-small output budget is consumed entirely by reasoning, so the turn ends
  with ``finish_reason="length"`` and no content at all;
* the server answers 503 ``{"error": {"message": "Loading model"}}`` for the
  minutes it spends cold-loading a multi-GB GGUF.

None of these tests touch the network — the SDK client is faked.
"""

from __future__ import annotations

from typing import Any

import pytest
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderCapability,
    ProviderErrorCode,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError

LOCAL_BASE_URL = "http://localhost:8086/v1"


def local_settings(**overrides: Any) -> ProviderSettings:
    return ProviderSettings(
        AEGIS_PROVIDER_LOCAL_BASE_URL=LOCAL_BASE_URL,
        AEGIS_PROVIDER_LOCAL_MODEL="local-reasoner.gguf",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST=LOCAL_BASE_URL,
        **overrides,
    )


def sample_request() -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="openai-compatible",
            model_id="openai-compatible-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="System prompt"),
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Triage the run"),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "confidence"],
                "additionalProperties": False,
            },
            strict=True,
            max_repair_attempts=0,
        ),
        capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
    )


class _FakeMessage:
    """Mimics the SDK message object, including its ``model_extra`` bag."""

    def __init__(
        self,
        *,
        content: str | None,
        reasoning_content: str | None = None,
        model_extra: dict[str, Any] | None = None,
    ) -> None:
        self.role = "assistant"
        self.content = content
        if reasoning_content is not None:
            self.reasoning_content = reasoning_content
        self.model_extra = model_extra or {}


class _FakeUsage:
    prompt_tokens = 12
    completion_tokens = 34
    total_tokens = 46


class _FakeChoice:
    def __init__(self, message: _FakeMessage, finish_reason: str) -> None:
        self.message = message
        self.finish_reason = finish_reason


class _FakeCompletion:
    def __init__(self, choice: _FakeChoice) -> None:
        self.choices = [choice]
        self.usage = _FakeUsage()


class _FakeCompletions:
    def __init__(self, result: Any) -> None:
        self._result = result

    async def create(self, **_kwargs: Any) -> Any:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeChat:
    def __init__(self, result: Any) -> None:
        self.completions = _FakeCompletions(result)


class _FakeClient:
    def __init__(self, result: Any) -> None:
        self.chat = _FakeChat(result)


def _completion(
    *,
    content: str | None,
    finish_reason: str = "stop",
    reasoning_content: str | None = None,
    model_extra: dict[str, Any] | None = None,
) -> _FakeCompletion:
    return _FakeCompletion(
        _FakeChoice(
            _FakeMessage(
                content=content,
                reasoning_content=reasoning_content,
                model_extra=model_extra,
            ),
            finish_reason,
        )
    )


def _provider(settings: ProviderSettings, result: Any) -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(settings)
    client = _FakeClient(result)
    provider._client = lambda: client  # type: ignore[method-assign]
    return provider


@pytest.mark.asyncio
async def test_reasoning_only_response_still_yields_structured_content() -> None:
    """A model that answers inside ``reasoning_content`` must not read as empty."""
    payload = '{"summary": "identity broker compromised", "confidence": 0.7}'
    provider = _provider(
        local_settings(),
        _completion(
            content="",
            reasoning_content=f"Let me think about the alerts.\n{payload}",
        ),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {
        "summary": "identity broker compromised",
        "confidence": 0.7,
    }


@pytest.mark.asyncio
async def test_reasoning_content_read_from_sdk_extra_fields() -> None:
    """The OpenAI SDK parks unknown fields in ``model_extra``, not an attribute."""
    payload = '{"summary": "vault isolated", "confidence": 0.4}'
    provider = _provider(
        local_settings(),
        _completion(content=None, model_extra={"reasoning_content": payload}),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "vault isolated", "confidence": 0.4}


@pytest.mark.asyncio
async def test_real_content_wins_over_reasoning_content() -> None:
    """Reasoning is only ever a fallback; a real answer is never overridden."""
    provider = _provider(
        local_settings(),
        _completion(
            content='{"summary": "real answer", "confidence": 0.9}',
            reasoning_content='{"summary": "scratch work", "confidence": 0.1}',
        ),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "real answer", "confidence": 0.9}


@pytest.mark.asyncio
async def test_inline_think_blocks_are_stripped_for_structured_output() -> None:
    """llama-server with ``--reasoning-format none`` inlines ``<think>`` into content.

    The scratchpad may contain stray braces, so the think block must be stripped
    before JSON parsing rather than recovered around.
    """
    payload = '{"summary": "gateway contained", "confidence": 0.8}'
    provider = _provider(
        local_settings(),
        _completion(content=f"<think>\nhmm {{not json\n</think>\n\n{payload}"),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "gateway contained", "confidence": 0.8}


@pytest.mark.asyncio
async def test_prose_response_with_inline_think_is_cleaned() -> None:
    """A prose turn must not leak the model's scratchpad to the operator."""
    provider = _provider(
        local_settings(),
        _completion(content="<think>reason reason</think>\n\nThe vault looks safe."),
    )
    request = sample_request().model_copy(
        update={"structured_output": None, "capabilities_required": []}
    )

    response = await provider.generate(request)

    assert response.content == "The vault looks safe."
    assert "<think>" not in (response.content or "")


@pytest.mark.asyncio
async def test_unclosed_think_block_still_recovers_structured_payload() -> None:
    """A turn that never leaves an unterminated scratchpad still yields its JSON."""
    payload = '{"summary": "broker compromised", "confidence": 0.6}'
    provider = _provider(
        local_settings(),
        _completion(content=f"<think>\nlet me reason\n{payload}"),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "broker compromised", "confidence": 0.6}


@pytest.mark.asyncio
async def test_local_provider_uses_prompt_schema_instead_of_server_grammar() -> None:
    """llama-server's json_schema grammar rejects the model's forced ``<think>`` opener.

    With ``--reasoning-format none`` the grammar constrains output from token one,
    but the chat template always begins with ``<think>`` — the request 400s with
    "Unexpected empty grammar stack". The local adapter therefore must not send
    ``response_format`` and instead instructs the model via a trailing message.
    """
    payload = '{"summary": "fine", "confidence": 0.5}'
    captured: dict[str, Any] = {}

    provider = _provider(local_settings(), _completion(content=payload))
    original = provider._client().chat.completions._result

    class _CapturingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return original

    provider._client().chat.completions = _CapturingCompletions()  # type: ignore[assignment]

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "fine", "confidence": 0.5}
    assert "response_format" not in captured
    last_message = captured["messages"][-1]
    assert "JSON" in last_message["content"]
    assert '"confidence"' in last_message["content"]


@pytest.mark.asyncio
async def test_output_budget_exhausted_by_reasoning_is_named_as_such() -> None:
    """Empty content + finish_reason=length is a token-budget fault, not a mystery."""
    provider = _provider(
        local_settings(),
        _completion(
            content="",
            reasoning_content="The user wants a triage summary. Let me consider",
            finish_reason="length",
        ),
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    error = exc_info.value.error
    assert error.code is ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED
    assert "reasoning" in error.message.lower()
    assert error.details.get("finishReason") == "length"


@pytest.mark.asyncio
async def test_cold_loading_endpoint_is_retryable_and_flagged_as_warming_up() -> None:
    """llama-server's cold-load 503 must be retryable with a warm-up backoff."""

    class _LoadingError(Exception):
        status_code = 503

        def __str__(self) -> str:
            return "Error code: 503 - {'error': {'message': 'Loading model', 'code': 503}}"

    provider = _provider(local_settings(), _LoadingError())

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    error = exc_info.value.error
    assert error.code is ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert error.retryable is True
    assert error.details.get("warmingUp") is True


@pytest.mark.asyncio
async def test_server_error_echoing_prompt_text_is_not_read_as_an_auth_failure() -> None:
    """Error classification must not substring-match text that carries our own data.

    AEGIS alerts are routinely titled "Authentication failed". When the classifier
    looked for "authentication" anywhere in the error string, a plain 500 on an
    incident about failed logins was reported to the operator as
    CREDENTIALS_MISSING — a wrong, non-retryable diagnosis that fails the task
    instantly and sends whoever reads it hunting for a missing API key.
    """

    class _ServerError(Exception):
        status_code = 500

        def __str__(self) -> str:
            return (
                "Error code: 500 - upstream failed while handling prompt: "
                "'Authentication failed on asset:svc-identity-broker'"
            )

    provider = _provider(local_settings(), _ServerError())

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    error = exc_info.value.error
    assert error.code is ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert error.retryable is True


@pytest.mark.asyncio
async def test_provider_error_detail_is_surfaced_redacted_and_bounded() -> None:
    """The provider's own message is the only diagnostic the operator can act on.

    Reporting just ``errorType: InternalServerError`` hid llama-server's actual
    complaint ("Failed to parse input at pos 6135: ...") — the difference between
    a diagnosable failure and a shrug. It is redacted and truncated because that
    text can echo the prompt.
    """

    class _ServerError(Exception):
        status_code = 500

        def __str__(self) -> str:
            return (
                "Error code: 500 - Failed to parse input at pos 6135: stray tag; "
                "api_key=sk-secret-value-should-not-survive " + "x" * 2000
            )

    provider = _provider(local_settings(), _ServerError())

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    detail = exc_info.value.error.details.get("providerMessage")
    assert isinstance(detail, str)
    assert "Failed to parse input at pos 6135" in detail
    assert "sk-secret-value-should-not-survive" not in detail
    assert len(detail) <= 512


@pytest.mark.asyncio
async def test_a_real_401_is_still_classified_as_missing_credentials() -> None:
    class _AuthError(Exception):
        status_code = 401

        def __str__(self) -> str:
            return "Error code: 401 - invalid key"

    provider = _provider(local_settings(), _AuthError())

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    assert exc_info.value.error.code is ProviderErrorCode.CREDENTIALS_MISSING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "content"),
    [
        ("fenced block", '```json\n{"summary": "fenced", "confidence": 0.5}\n```'),
        ("prose preamble", 'Here is the result:\n{"summary": "fenced", "confidence": 0.5}'),
        (
            "trailing commentary",
            '{"summary": "fenced", "confidence": 0.5}\nTell me if you need more.',
        ),
        ("trailing comma", '{"summary": "fenced", "confidence": 0.5,}'),
        (
            "think block then a fenced object",
            '<think>weighing it up</think>\n```json\n{"summary": "fenced", "confidence": 0.5}\n```',
        ),
    ],
)
async def test_near_miss_json_shapes_are_recovered_rather_than_failed(
    label: str, content: str
) -> None:
    """The prompt says "no code fences, no prose" and the model does it anyway.

    With no server-side grammar the model is only *asked* to emit bare JSON, so
    every one of these shapes shows up live. Each wraps an answer that is present
    and correct, and failing the turn over the wrapper throws away a model call
    that already succeeded — on this endpoint, a minute of one.
    """
    provider = _provider(local_settings(), _completion(content=content))

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "fenced", "confidence": 0.5}, label


@pytest.mark.asyncio
async def test_schema_invalid_output_is_returned_for_repair_not_raised() -> None:
    """The adapter must not fail the call over a payload the model could fix.

    This is the bug that made ``max_repair_attempts`` dead configuration: the
    adapter validated and raised, so ``GenerationService`` never saw a response
    there was anything to repair. Handing the raw content back with
    ``structured_data`` unset is the signal the repair path keys on.
    """
    provider = _provider(
        local_settings(),
        _completion(content='{"summary": "no confidence field"}'),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data is None
    assert response.content == '{"summary": "no confidence field"}'


@pytest.mark.asyncio
async def test_a_truncated_object_is_named_as_a_token_budget_fault() -> None:
    """Measured live: a WATCHTOWER turn spends its whole output budget and stops.

    ``finish_reason=length`` with an unfinished object is a token-budget fault,
    and the operator can act on that. Reporting it as "Model output is not valid
    JSON" — which is what happened before, because the truncated text simply
    failed to parse — sends them to look at the schema instead. Repair is also
    pointless here: the same budget truncates the same way.
    """
    provider = _provider(
        local_settings(),
        _completion(
            content='{"summary": "the identity broker was com',
            finish_reason="length",
        ),
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request())

    error = exc_info.value.error
    assert error.code is ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED
    assert error.retryable is False
    assert error.details.get("truncated") is True
    assert error.details.get("maxOutputTokens")


@pytest.mark.asyncio
async def test_a_complete_object_followed_by_truncated_prose_still_succeeds() -> None:
    """Only a turn with no *usable* payload is a budget fault."""
    provider = _provider(
        local_settings(),
        _completion(
            content='{"summary": "done", "confidence": 0.9}\nAdditionally I would rec',
            finish_reason="length",
        ),
    )

    response = await provider.generate(sample_request())

    assert response.structured_data == {"summary": "done", "confidence": 0.9}


@pytest.mark.asyncio
async def test_client_is_built_with_a_bounded_timeout_and_no_hidden_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SDK's 600s default timeout and 2 silent retries would blow any budget."""
    import openai

    captured: dict[str, Any] = {}

    class _Recorder:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(openai, "AsyncOpenAI", _Recorder)

    provider = OpenAICompatibleProvider(local_settings(AEGIS_PROVIDER_TIMEOUT_SECONDS=45))
    provider._client()

    assert captured["max_retries"] == 0
    assert float(captured["timeout"]) == pytest.approx(45.0)
