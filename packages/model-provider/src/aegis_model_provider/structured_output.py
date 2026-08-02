"""Structured output recovery, validation, and bounded repair."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ProviderErrorCode,
    StructuredOutputSpecV1,
)
from jsonschema import Draft202012Validator

from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error

#: How much of a malformed answer is echoed back to the model in a repair prompt.
#: The whole thing can be the model's entire output budget, and re-sending that
#: verbatim doubles the prompt for a turn that already ran long.
MAX_REPAIR_ECHO_CHARS = 2000


def iter_balanced_json_objects(text: str) -> Iterator[str]:
    """Every balanced ``{...}`` span in ``text``, left to right.

    A model that wraps its answer in prose, a `````json`` fence, or its own
    commentary still emits one object-shaped span; scanning for balanced braces
    recovers it without guessing at delimiters. Spans are yielded rather than
    just the first, because the prose *before* the answer routinely contains
    brace-shaped text of its own ("pass {limit: 50}") that would otherwise be
    mistaken for the payload.
    """
    index = 0
    length = len(text)
    while index < length:
        start = text.find("{", index)
        if start < 0:
            return
        depth = 0
        in_string = False
        escaped = False
        for position in range(start, length):
            char = text[position]
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
                    yield text[start : position + 1]
                    break
        else:
            # Unterminated: nothing further in this text can balance either.
            return
        index = position + 1


def strip_trailing_commas(text: str) -> str:
    """Drop ``,`` that sits immediately before a ``}``/``]``, outside strings.

    A trailing comma is the single most common way a local model's otherwise
    perfect object fails ``json.loads``, and dropping one cannot change the
    meaning of a document that would otherwise be valid.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    length = len(text)
    for index, char in enumerate(text):
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            out.append(char)
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and text[lookahead] in "}]":
                continue
        out.append(char)
    return "".join(out)


def _json_candidates(text: str) -> Iterator[str]:
    stripped = text.strip()
    if stripped:
        yield stripped
    yield from iter_balanced_json_objects(text)


def recover_json_object(text: str | None) -> dict[str, Any] | None:
    """Best-effort JSON object from output that is JSON, or nearly JSON.

    The local endpoint serves a reasoning model with no server-side grammar, so
    the contract is enforced entirely on this side and the model routinely misses
    it in recoverable ways: a fenced `````json`` block, a sentence of
    preamble, commentary after the closing brace, a trailing comma. Each of those
    is a formatting slip around an answer that is otherwise present and correct,
    and failing the turn over one wastes a model call that already succeeded.

    Returns ``None`` when nothing object-shaped parses — a genuinely unusable
    answer, which the caller reports (and may repair) rather than guesses at.
    """
    if not text:
        return None
    for candidate in _json_candidates(text):
        for attempt in (candidate, strip_trailing_commas(candidate)):
            try:
                parsed = json.loads(attempt)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                return parsed
            break
    return None


def recover_json_text(text: str | None) -> str | None:
    """:func:`recover_json_object` re-serialized, for callers that carry text."""
    recovered = recover_json_object(text)
    return None if recovered is None else json.dumps(recovered)


def parse_json_content(content: str) -> dict[str, Any]:
    """Strictly parse ``content`` as a JSON object, or raise.

    Kept strict — :func:`recover_json_object` is the lenient path, and callers
    choose which contract they want.
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
                message="Model output is not valid JSON",
                details={"error": str(exc)},
            )
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
                message="Structured output must be a JSON object",
            )
        )
    return parsed


def parse_structured_content(content: str) -> dict[str, Any]:
    """Recover a JSON object from model output, raising the strict error if none.

    This is the pairing every structured-output caller wants: try every
    recoverable shape first, and when none of them yields an object report the
    same ``STRUCTURED_OUTPUT_INVALID`` the strict parser would have.
    """
    recovered = recover_json_object(content)
    if recovered is not None:
        return recovered
    return parse_json_content(content)


def validate_structured_output(
    data: dict[str, Any],
    spec: StructuredOutputSpecV1,
) -> dict[str, Any]:
    validator = Draft202012Validator(spec.json_schema)
    errors = sorted(validator.iter_errors(data), key=lambda item: item.path)
    if errors:
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
                message="Structured output failed schema validation",
                details={
                    "validationErrors": [
                        {"path": list(error.path), "message": error.message} for error in errors[:5]
                    ]
                },
            )
        )
    return data


def build_repair_messages(
    request: GenerationRequestV1,
    *,
    invalid_content: str,
    validation_message: str,
    validation_details: dict[str, Any] | None = None,
) -> list[GenerationMessageV1]:
    """The original turn plus one corrective exchange.

    The model is shown its own rejected answer and the specific complaint, which
    is what makes a repair different from simply asking again: a local model that
    dropped a required field or fenced its object usually fixes exactly that when
    told which one it was.
    """
    errors = (validation_details or {}).get("validationErrors")
    detail = ""
    if isinstance(errors, list) and errors:
        detail = " Specifically: " + "; ".join(
            f"{'/'.join(str(part) for part in item.get('path') or []) or '<root>'}: "
            f"{item.get('message')}"
            for item in errors
            if isinstance(item, dict)
        )
    repair_prompt = (
        "Your previous output failed validation: "
        f"{validation_message}.{detail} "
        "Respond with ONLY the corrected JSON object — no code fences, no prose, "
        "no commentary — matching the schema you were given."
    )
    echoed = invalid_content[:MAX_REPAIR_ECHO_CHARS]
    return [
        *request.messages,
        GenerationMessageV1(role=GenerationMessageRole.ASSISTANT, content=echoed),
        GenerationMessageV1(role=GenerationMessageRole.USER, content=repair_prompt),
    ]
