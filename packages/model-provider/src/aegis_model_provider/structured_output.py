"""Structured output validation and bounded repair."""

from __future__ import annotations

import json
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


def parse_json_content(content: str) -> dict[str, Any]:
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
) -> list[GenerationMessageV1]:
    repair_prompt = (
        "The previous response was invalid. Return only valid JSON that matches the schema. "
        f"Validation error: {validation_message}"
    )
    return [
        *request.messages,
        GenerationMessageV1(role=GenerationMessageRole.ASSISTANT, content=invalid_content),
        GenerationMessageV1(role=GenerationMessageRole.USER, content=repair_prompt),
    ]
