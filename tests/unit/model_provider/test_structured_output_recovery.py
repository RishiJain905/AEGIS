"""Recovering structured output from a local model that nearly followed its schema.

The local endpoint serves a reasoning model with **no server-side grammar** — the
adapter opts out of ``response_format`` because llama-server's json_schema grammar
cannot coexist with the model's forced ``<think>`` opener. The whole contract is
therefore enforced on this side, and the model misses it constantly in shapes that
are recoverable: a fenced ```` ```json ```` block, a sentence of preamble, a
closing remark after the object, a trailing comma.

Every one of those used to fail the turn outright with "Model output is not valid
JSON". These tests pin the recovery ladder that keeps such a turn, and the ONE
bounded repair round-trip that answers the genuinely malformed rest — with a hard
ceiling, because an unbounded repair loop against a slow local model is a cost bug
wearing a robustness costume.

No network anywhere: the provider is a scripted fake.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ModelConfigV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
    ProviderFinishReason,
    ProviderUsageV1,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    GENERATION_RESPONSE_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.registry import ProviderRegistry
from aegis_model_provider.service import MAX_REPAIR_ROUNDS, GenerationService
from aegis_model_provider.structured_output import (
    iter_balanced_json_objects,
    recover_json_object,
    strip_trailing_commas,
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["summary", "confidence"],
    "additionalProperties": False,
}

_VALID = {"summary": "identity broker compromised", "confidence": 0.7}
_NOW = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)


# --- the recovery ladder ------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("bare object", '{"summary": "s", "confidence": 0.5}'),
        (
            "fenced code block",
            '```json\n{"summary": "s", "confidence": 0.5}\n```',
        ),
        (
            "bare fence with no language tag",
            '```\n{"summary": "s", "confidence": 0.5}\n```',
        ),
        (
            "prose preamble",
            'Here is the triage result:\n\n{"summary": "s", "confidence": 0.5}',
        ),
        (
            "trailing commentary",
            '{"summary": "s", "confidence": 0.5}\n\nLet me know if you need more detail.',
        ),
        (
            "prose on both sides",
            'Sure!\n{"summary": "s", "confidence": 0.5}\nHope that helps.',
        ),
        (
            "trailing comma before the closing brace",
            '{"summary": "s", "confidence": 0.5,}',
        ),
        (
            "trailing comma inside a nested array",
            '{"summary": "s", "confidence": 0.5, "tags": ["a", "b",],}',
        ),
        (
            "brace-shaped prose before the real object",
            'Call it with {limit: 50} first.\n{"summary": "s", "confidence": 0.5}',
        ),
    ],
)
def test_recoverable_shapes_yield_the_object(label: str, text: str) -> None:
    recovered = recover_json_object(text)
    assert recovered is not None, label
    assert recovered["summary"] == "s"
    assert recovered["confidence"] == 0.5


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("empty", ""),
        ("none", None),
        ("pure prose", "I could not complete the triage for this incident."),
        ("truncated mid-object", '{"summary": "s", "confidence": 0.'),
        ("a bare array, not an object", '["summary", "confidence"]'),
        ("single-quoted pseudo-JSON", "{'summary': 's', 'confidence': 0.5}"),
    ],
)
def test_unrecoverable_shapes_return_none(label: str, text: str | None) -> None:
    """Recovery must never guess.

    Single quotes are deliberately NOT repaired here: apostrophes inside prose
    make that transform ambiguous, and a wrong guess persists a payload the model
    never wrote. Those shapes go to the repair round-trip instead.
    """
    assert recover_json_object(text) is None, label


def test_recovery_does_not_mangle_braces_inside_strings() -> None:
    text = 'noise {"summary": "use {curly} braces, \\"quoted\\" too", "confidence": 0.1} tail'
    recovered = recover_json_object(text)
    assert recovered is not None
    assert recovered["summary"] == 'use {curly} braces, "quoted" too'


def test_trailing_comma_stripping_leaves_commas_inside_strings_alone() -> None:
    assert strip_trailing_commas('{"a": "x, y",}') == '{"a": "x, y"}'
    assert strip_trailing_commas('{"a": "trailing, "}') == '{"a": "trailing, "}'


def test_balanced_scan_yields_each_top_level_object_once() -> None:
    spans = list(iter_balanced_json_objects('{"a": {"b": 1}} then {"c": 2}'))
    assert spans == ['{"a": {"b": 1}}', '{"c": 2}']


# --- the bounded repair round-trip -------------------------------------------


def _request(*, max_repair_attempts: int = 1) -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id="fake",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="fake",
            model_id="fake-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="System prompt"),
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Triage the run"),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema=_SCHEMA,
            strict=True,
            max_repair_attempts=max_repair_attempts,
        ),
        capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
    )


class _ScriptedProvider:
    """Returns raw content per call, exactly as a schema-less adapter does.

    ``structured_data`` is left unset on every turn — that is the signal the real
    adapters now emit for output they could not validate, and the signal the
    service's repair path keys on.
    """

    provider_id = "fake"

    def __init__(self, script: list[str]) -> None:
        self._script = script
        self.requests: list[GenerationRequestV1] = []

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[ProviderCapability.STRUCTURED_OUTPUT, ProviderCapability.TOOLS],
        )

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        content = self._script[min(len(self.requests), len(self._script) - 1)]
        self.requests.append(request)
        return GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_id=self.provider_id,
            model_id="fake-v1",
            prompt_version="phase18-v1",
            content=content,
            structured_data=None,
            finish_reason=ProviderFinishReason.STOP,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            ),
            latency_ms=1,
            completed_at=_NOW,
        )


def _service(provider: _ScriptedProvider) -> GenerationService:
    return GenerationService(
        registry=ProviderRegistry({"fake": provider}, default_provider_id="fake"),
        settings=ProviderSettings(AEGIS_PROVIDER_MAX_RETRIES=0),
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )


@pytest.mark.asyncio
async def test_schema_invalid_output_is_repaired_in_one_round_trip() -> None:
    """The behaviour that was unreachable before.

    The adapter used to raise on a schema-invalid payload, so the service's
    repair machinery never saw a response there was anything to repair — the
    request asked for ``max_repair_attempts=1`` and got zero attempts.
    """
    provider = _ScriptedProvider(
        [
            json.dumps({"summary": "missing its confidence"}),
            json.dumps(_VALID),
        ]
    )
    result = await _service(provider).generate(_request(), dry_run=True)

    assert result.error is None
    assert result.response is not None
    assert result.response.structured_data == _VALID
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_the_repair_prompt_shows_the_model_its_own_output_and_the_complaint() -> None:
    """A repair that does not say what was wrong is just asking again."""
    provider = _ScriptedProvider(
        [json.dumps({"summary": "missing its confidence"}), json.dumps(_VALID)]
    )
    await _service(provider).generate(_request(), dry_run=True)

    repair = provider.requests[1]
    assistant = [m for m in repair.messages if m.role is GenerationMessageRole.ASSISTANT]
    assert assistant and "missing its confidence" in assistant[-1].content
    final = repair.messages[-1].content
    assert "failed validation" in final
    assert "confidence" in final
    assert "ONLY the corrected JSON object" in final


@pytest.mark.asyncio
async def test_unparseable_output_is_also_repaired() -> None:
    provider = _ScriptedProvider(["I cannot produce JSON right now.", json.dumps(_VALID)])
    result = await _service(provider).generate(_request(), dry_run=True)

    assert result.error is None
    assert result.response is not None
    assert result.response.structured_data == _VALID


@pytest.mark.asyncio
async def test_repair_is_attempted_at_most_once_however_bad_the_model_is() -> None:
    """The cost bound. A model that cannot follow its schema costs ONE extra call.

    The request asks for the contract's maximum (2) and still gets one, because
    the ceiling belongs to the service: a slow local endpoint turns every extra
    round into tens of seconds spent against a caller's deadline, whatever the
    request thought it wanted.
    """
    provider = _ScriptedProvider(["not json at all"])
    result = await _service(provider).generate(
        _request(max_repair_attempts=2),
        dry_run=True,
    )

    assert len(provider.requests) == 1 + MAX_REPAIR_ROUNDS == 2
    assert result.error is not None
    assert result.error.code is ProviderErrorCode.STRUCTURED_OUTPUT_INVALID


@pytest.mark.asyncio
async def test_a_failed_repair_reports_the_original_complaint_not_the_second_one() -> None:
    """The first failure is the one that describes what the model got wrong."""
    provider = _ScriptedProvider([json.dumps({"summary": "no confidence field"}), "gibberish"])
    result = await _service(provider).generate(_request(), dry_run=True)

    assert result.error is not None
    assert result.error.message == "Structured output failed schema validation"
    assert result.error.details.get("repairAttempted") is True


@pytest.mark.asyncio
async def test_no_repair_is_spent_when_the_request_forbids_it() -> None:
    provider = _ScriptedProvider(["not json at all"])
    result = await _service(provider).generate(
        _request(max_repair_attempts=0),
        dry_run=True,
    )

    assert len(provider.requests) == 1
    assert result.error is not None
    assert result.error.code is ProviderErrorCode.STRUCTURED_OUTPUT_INVALID
    assert "repairAttempted" not in result.error.details


@pytest.mark.asyncio
async def test_a_recoverable_shape_costs_no_repair_call_at_all() -> None:
    """Recovery runs first precisely so the common case stays a single call."""
    provider = _ScriptedProvider([f"Here you go:\n```json\n{json.dumps(_VALID)}\n```"])
    result = await _service(provider).generate(_request(), dry_run=True)

    assert len(provider.requests) == 1
    assert result.error is None
    assert result.response is not None
    assert result.response.structured_data == _VALID


@pytest.mark.asyncio
async def test_a_provider_error_during_repair_does_not_mask_the_real_failure() -> None:
    """A repair attempt can only ever improve the turn, never worsen its report."""

    class _ExplodingOnRepair(_ScriptedProvider):
        async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
            if self.requests:
                self.requests.append(request)
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                        message="local model went away",
                    )
                )
            return await super().generate(request)

    provider = _ExplodingOnRepair([json.dumps({"summary": "no confidence field"})])
    result = await _service(provider).generate(_request(), dry_run=True)

    assert result.error is not None
    assert result.error.code is ProviderErrorCode.STRUCTURED_OUTPUT_INVALID
    assert result.error.message == "Structured output failed schema validation"
