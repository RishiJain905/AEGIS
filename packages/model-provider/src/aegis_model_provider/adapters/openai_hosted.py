"""OpenAI hosted provider adapter."""

from __future__ import annotations

import inspect
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
from aegis_model_provider.structured_output import (
    recover_json_object,
    recover_json_text,
    validate_structured_output,
)


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

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        base_url: str | None = None,
        api_key_override: str | None = None,
        model_id_override: str | None = None,
    ) -> None:
        """``*_override`` carry per-call credentials — a run owner's stored API key and
        the model their loadout pinned — which outrank the environment defaults.

        Deliberately no destination override: the base URL comes from settings and is
        still checked against the egress allowlist here, so supplying a credential can
        never become a way to reach an unlisted host.
        """
        self._settings = settings
        self._api_key_override = api_key_override
        self._model_id_override = model_id_override
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

    def _configured_api_key(self) -> str | None:
        """The environment's key for this adapter; subclasses point at their own var."""
        return self._settings.AEGIS_PROVIDER_OPENAI_API_KEY

    def _api_key(self) -> str:
        api_key = (self._api_key_override or self._configured_api_key() or "").strip()
        if not api_key:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CREDENTIALS_MISSING,
                    message=f"No API key is configured for provider '{self.provider_id}'",
                    details={"providerId": self.provider_id},
                )
            )
        return api_key

    def _client(self) -> Any:
        api_key = self._api_key()
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
            api_key=api_key,
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

    def _default_model_id(self) -> str:
        """The model to use when the request names no real one. Override beats env."""
        return self._model_id_override or self._settings.AEGIS_PROVIDER_OPENAI_MODEL

    def _resolve_model_id(self, request: GenerationRequestV1) -> str:
        # Agent definitions carry synthetic ids like "openrouter-v1" (the runtime builds
        # them from the provider id), which no real endpoint serves. Those defer to the
        # pinned override or the env default; a request naming a real model still wins.
        requested = request.model_config_ref.model_id
        if requested and requested != f"{self.provider_id}-v1":
            return requested
        return self._default_model_id()

    async def list_models(self) -> list[str]:
        """The endpoint's catalogue, deduplicated and sorted.

        The loadout dialog offers whatever the operator's own subscription serves, so
        the list has to come from the provider rather than a hardcoded table. It goes
        through the adapter (not ad-hoc HTTP) to keep the egress allowlist and the
        credential seam on one path.
        """
        client = self._client()
        try:
            page = await client.models.list()
        except Exception as exc:
            message = str(exc)
            if _is_auth_failure(message, exc):
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.CREDENTIALS_MISSING,
                        message=f"Provider '{self.provider_id}' rejected the API key",
                        details={"providerId": self.provider_id, "errorType": type(exc).__name__},
                    )
                ) from exc
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Provider '{self.provider_id}' model listing failed",
                    retryable=True,
                    details={
                        "providerId": self.provider_id,
                        "errorType": type(exc).__name__,
                        "providerMessage": _provider_message(message),
                    },
                )
            ) from exc
        finally:
            await self._close_client(client)
        return sorted({str(entry.id).strip() for entry in page.data if str(entry.id).strip()})

    @staticmethod
    async def _close_client(client: Any) -> None:
        # A listing client is built for one call; without this its httpx pool leaks.
        close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    #: Whether structured requests ride the server's ``response_format`` grammar.
    #: llama-server cannot combine a json_schema grammar with a reasoning model whose
    #: chat template opens with ``<think>`` — the grammar constrains output from the
    #: first token and rejects it ("Unexpected empty grammar stack"). The local
    #: adapter opts out and instructs the model in-prompt instead; the client-side
    #: extraction + validation pipeline enforces the contract either way.
    _use_server_response_format = True

    @staticmethod
    def _structured_data(
        request: GenerationRequestV1,
        *,
        content: str,
        finish_reason: ProviderFinishReason,
        max_output_tokens: int,
    ) -> dict[str, Any] | None:
        """The validated payload, or ``None`` to hand the turn to the repair path.

        Recovery covers the formatting slips a prompt-side schema invites — a
        fenced block, a sentence of preamble, commentary after the closing brace,
        a trailing comma — because each of those wraps an answer that is present
        and correct.

        What this must NOT do is raise on a *schema-invalid* payload. A model that
        dropped a required field can usually put it back when told which one, and
        ``GenerationService`` owns that one bounded repair round-trip. Raising here
        is what made repair unreachable: the adapter failed the call before the
        service ever saw a response there was anything to repair.

        Truncation is the exception. ``finish_reason=length`` with no *usable*
        payload — nothing recoverable, or a fragment that fails the schema —
        means the answer was cut off mid-write, so re-prompting under the same
        budget would only truncate again. Measured against the live local model,
        a WATCHTOWER-sized turn spent all 4096 output tokens inside its own
        scratchpad and emitted no JSON at all; naming that as a token-budget
        fault is the diagnosis operators were missing when it surfaced as the
        far more mysterious "Model output is not valid JSON".
        """
        assert request.structured_output is not None
        recovered = recover_json_object(content)
        if recovered is not None:
            try:
                return validate_structured_output(recovered, request.structured_output)
            except ProviderRuntimeError:
                # Well-formed but schema-invalid: repairable, unless the reason it
                # is wrong is that the model ran out of room to finish it.
                pass
        if finish_reason is ProviderFinishReason.LENGTH:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED,
                    message=(
                        "Provider output was truncated before it finished the JSON "
                        "object; raise the output token budget"
                    ),
                    retryable=False,
                    details={
                        "finishReason": "length",
                        "maxOutputTokens": max_output_tokens,
                        "truncated": True,
                    },
                    trace_id=request.trace_id,
                )
            )
        return None

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
                recover_json_text(reasoning)
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
            structured_data = self._structured_data(
                request,
                content=content,
                finish_reason=finish_reason,
                max_output_tokens=int(kwargs["max_tokens"]),
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
