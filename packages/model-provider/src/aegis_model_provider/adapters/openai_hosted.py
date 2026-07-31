"""OpenAI hosted provider adapter."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from aegis_contracts.generation import (
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
    ProviderFinishReason,
    ProviderUsageV1,
)
from aegis_contracts.versioning import (
    GENERATION_RESPONSE_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
)

from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.cost import with_estimated_cost
from aegis_model_provider.egress import assert_provider_destination_allowed
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.redaction import redact_string
from aegis_model_provider.structured_output import parse_json_content, validate_structured_output


def _map_finish_reason(value: str | None) -> ProviderFinishReason:
    if value in {"stop", "tool_calls", "length", "content_filter"}:
        return ProviderFinishReason(value)
    return ProviderFinishReason.ERROR


def _reasoning_content(message: Any) -> str:
    """The reasoning channel of a reasoning model, however the SDK exposed it.

    ``reasoning_content`` is not an OpenAI field, so a strict SDK model parks it
    in ``model_extra`` while a permissive one sets it as an attribute. Read both.
    """
    value = getattr(message, "reasoning_content", None)
    if not value:
        extra = getattr(message, "model_extra", None) or {}
        value = extra.get("reasoning_content") if isinstance(extra, dict) else None
    return value if isinstance(value, str) else ""


_THINK_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _split_think_blocks(text: str) -> tuple[str, str]:
    """``(visible, scratchpad)`` for content carrying inline ``<think>`` blocks.

    llama-server launched with ``--reasoning-format none`` stops parsing reasoning
    server-side and hands the raw scratchpad through inside ``content`` — the shape
    that made its parser 500 on this model's stray tags is avoided by moving the
    split here. Closed blocks are cut out wholesale; an unterminated ``<think>``
    means the model never left its scratchpad, so everything after the tag is
    scratchpad too, and the visible remainder may legitimately be empty.
    """
    if "<think>" not in text:
        return text, ""
    scratch = [match.group(1) for match in _THINK_BLOCK.finditer(text)]
    visible = _THINK_BLOCK.sub("", text)
    head, sep, tail = visible.partition("<think>")
    if sep:
        scratch.append(tail)
        visible = head
    return visible.strip(), "\n".join(part.strip() for part in scratch if part.strip())


def _extract_json_object(text: str) -> str | None:
    """The outermost balanced ``{...}`` in ``text``, if there is one.

    A reasoning model that answers inside its scratchpad wraps the payload in
    prose. Scanning for a balanced object recovers it without guessing at
    delimiters; ``None`` means there was nothing object-shaped to recover.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


MAX_PROVIDER_MESSAGE_CHARS = 512


def _provider_message(message: str) -> str:
    """The provider's own complaint, safe to show an operator.

    Redacted because this text routinely echoes the prompt, and truncated because
    llama-server embeds the model's whole malformed output in a parse error.
    Without it a failure reads only as ``errorType: InternalServerError``, which
    is exactly the missing "provider diagnostics" the QA pass called out.
    """
    redacted = redact_string(message).strip()
    if len(redacted) > MAX_PROVIDER_MESSAGE_CHARS:
        redacted = redacted[: MAX_PROVIDER_MESSAGE_CHARS - 1].rstrip() + "…"
    return redacted


def _is_auth_failure(message: str, exc: Exception) -> bool:
    """Whether the provider rejected our credentials.

    Deliberately NOT a substring search over the error text. That text routinely
    echoes the prompt, and AEGIS alerts are titled things like "Authentication
    failed on asset:svc-identity-broker" — so a plain 500 on an authentication
    incident was being reported as CREDENTIALS_MISSING, which is both wrong and
    non-retryable. Status code first, then the SDK's own exception type.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in {401, 403}
    if type(exc).__name__ in {"AuthenticationError", "PermissionDeniedError"}:
        return True
    # No status and no typed exception to go on: fall back to the message, but
    # only for phrasings that describe OUR credentials rather than the payload's.
    lowered = message.lower()
    return "invalid api key" in lowered or "incorrect api key" in lowered


def _is_model_loading(message: str, exc: Exception) -> bool:
    """Whether the endpoint 503'd because it is still loading its weights.

    llama-server lazy-loads the GGUF on the first request and answers
    ``503 {"error": {"message": "Loading model"}}`` for as long as that takes.
    That is a warm-up, not an outage, and it deserves a warm-up backoff.
    """
    if getattr(exc, "status_code", None) == 503 or "503" in message:
        return True
    lowered = message.lower()
    return "loading model" in lowered or "model is loading" in lowered


class OpenAIHostedProvider:
    provider_id = "openai"

    def __init__(self, settings: ProviderSettings, *, base_url: str | None = None) -> None:
        self._settings = settings
        configured_base_url = (
            settings.AEGIS_PROVIDER_OPENAI_BASE_URL if base_url is None else base_url
        )
        self._base_url = assert_provider_destination_allowed(
            base_url=configured_base_url,
            allowed_base_urls=settings.provider_egress_allowlist,
            provider_id=self.provider_id,
        )

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[
                ProviderCapability.STRUCTURED_OUTPUT,
                ProviderCapability.TOOLS,
            ],
        )

    def _client(self) -> Any:
        if not self._settings.AEGIS_PROVIDER_OPENAI_API_KEY.strip():
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CREDENTIALS_MISSING,
                    message="OpenAI provider credentials are not configured",
                    details={"providerId": self.provider_id},
                )
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.INTERNAL,
                    message="OpenAI SDK is not installed",
                )
            ) from exc
        return AsyncOpenAI(
            api_key=self._settings.AEGIS_PROVIDER_OPENAI_API_KEY,
            base_url=self._base_url,
            **self._client_options(),
        )

    def _client_options(self) -> dict[str, Any]:
        """Transport bounds the resilience layer needs the SDK to honour.

        Left to its defaults the SDK applies a 600s timeout and TWO silent
        retries of its own, so a single ``generate`` can consume 30 minutes of
        wall clock that no caller budgeted for. Retries belong to
        ``run_with_resilience``, which knows the deadline; the SDK just needs to
        stop at the per-attempt ceiling and report.
        """
        return {
            "timeout": float(self._settings.AEGIS_PROVIDER_TIMEOUT_SECONDS),
            "max_retries": 0,
        }

    def _resolve_model_id(self, request: GenerationRequestV1) -> str:
        return request.model_config_ref.model_id or self._settings.AEGIS_PROVIDER_OPENAI_MODEL

    #: Whether structured requests ride the server's ``response_format`` grammar.
    #: llama-server cannot combine a json_schema grammar with a reasoning model whose
    #: chat template opens with ``<think>`` — the grammar constrains output from the
    #: first token and rejects it ("Unexpected empty grammar stack"). The local
    #: adapter opts out and instructs the model in-prompt instead; the client-side
    #: extraction + validation pipeline enforces the contract either way.
    _use_server_response_format = True

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        client = self._client()
        model_id = self._resolve_model_id(request)
        messages = [
            {"role": message.role.value, "content": message.content} for message in request.messages
        ]
        if request.structured_output is not None and not self._use_server_response_format:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Respond with ONLY a single JSON object — no code fences, no "
                        "prose — that validates against this JSON Schema:\n"
                        + json.dumps(request.structured_output.json_schema)
                    ),
                }
            )
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": min(
                request.max_output_tokens, self._settings.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS
            ),
        }
        if request.model_config_ref.temperature is not None:
            kwargs["temperature"] = request.model_config_ref.temperature
        if request.structured_output is not None and self._use_server_response_format:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "aegis_structured_output",
                    "schema": request.structured_output.json_schema,
                    "strict": request.structured_output.strict,
                },
            }
        started = datetime.now(UTC)
        try:
            completion = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            error_type = type(exc).__name__
            message = str(exc)
            if _is_auth_failure(message, exc):
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.CREDENTIALS_MISSING,
                        message="OpenAI authentication failed",
                        details={"errorType": error_type},
                        trace_id=request.trace_id,
                    )
                ) from exc
            if "timeout" in message.lower():
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.TIMEOUT,
                        message="OpenAI request timed out",
                        retryable=True,
                        trace_id=request.trace_id,
                    )
                ) from exc
            warming_up = _is_model_loading(message, exc)
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                    message=(
                        "Provider endpoint is still loading the model"
                        if warming_up
                        else "OpenAI provider request failed"
                    ),
                    retryable=True,
                    details=(
                        {
                            "errorType": error_type,
                            "providerMessage": _provider_message(message),
                            "warmingUp": True,
                        }
                        if warming_up
                        else {
                            "errorType": error_type,
                            "providerMessage": _provider_message(message),
                        }
                    ),
                    trace_id=request.trace_id,
                )
            ) from exc

        choice = completion.choices[0]
        finish_reason = _map_finish_reason(choice.finish_reason)
        content, inline_think = _split_think_blocks(choice.message.content or "")
        reasoning = _reasoning_content(choice.message) or inline_think
        if not content and reasoning:
            # A reasoning model can end its turn without ever leaving the
            # scratchpad, so the whole answer sits in ``reasoning_content`` with
            # ``content`` empty. Recovering the payload from there is the
            # difference between a usable turn and a hard PROVIDER_FAILURE. Plain
            # prose recovers as-is; a structured request takes the JSON object out
            # of the surrounding thinking.
            recovered = (
                _extract_json_object(reasoning)
                if request.structured_output is not None
                else reasoning.strip()
            )
            if recovered:
                content = recovered
        if not content and finish_reason is ProviderFinishReason.LENGTH:
            # Reasoning consumed the entire output budget. Naming that is what
            # makes it fixable — the generic "empty structured output" sent
            # operators looking at the schema instead of at max_output_tokens.
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED,
                    message=(
                        "Provider spent its entire output budget on reasoning and "
                        "returned no content; raise the output token budget"
                    ),
                    retryable=False,
                    details={
                        "finishReason": "length",
                        "maxOutputTokens": kwargs["max_tokens"],
                        "reasoningTokens": bool(reasoning),
                    },
                    trace_id=request.trace_id,
                )
            )
        structured_data = None
        if request.structured_output is not None and content:
            structured_data = validate_structured_output(
                parse_json_content(content),
                request.structured_output,
            )
        usage = with_estimated_cost(
            model_id=model_id,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=completion.usage.prompt_tokens if completion.usage else 0,
                completion_tokens=completion.usage.completion_tokens if completion.usage else 0,
                total_tokens=completion.usage.total_tokens if completion.usage else 0,
            ),
        )
        latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        return GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_id=self.provider_id,
            model_id=model_id,
            prompt_version=request.model_config_ref.prompt_version,
            content=content,
            structured_data=structured_data,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            completed_at=datetime.now(UTC),
        )
