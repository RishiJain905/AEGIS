#!/usr/bin/env python3
"""Run Phase 18 provider harness checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderCapability,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService


def build_sample_request(*, provider_id: str, invalid: bool = False) -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id=provider_id,
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id=provider_id,
            model_id=f"{provider_id}-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="System prompt"),
            GenerationMessageV1(
                role=GenerationMessageRole.USER,
                content="Return invalid structured output please"
                if invalid
                else "Summarize",
            ),
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


async def run_harness(adapter: str) -> int:
    settings = load_provider_settings()
    registry = build_provider_registry(settings)
    service = GenerationService(
        registry=registry,
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )

    checks: list[tuple[str, object]] = []

    mock_result = await service.generate(build_sample_request(provider_id="mock"), dry_run=True)
    checks.append(("mock", mock_result.model_dump(by_alias=True, mode="json")))

    recorded_result = await service.generate(
        build_sample_request(provider_id="recorded"), dry_run=True
    )
    checks.append(("recorded", recorded_result.model_dump(by_alias=True, mode="json")))

    invalid_result = await service.generate(
        build_sample_request(provider_id="mock", invalid=True),
        dry_run=True,
    )
    checks.append(
        ("invalid_structured_output", invalid_result.model_dump(by_alias=True, mode="json"))
    )

    if adapter in {"openai", "all"}:
        openai_result = await service.generate(
            build_sample_request(provider_id="openai").model_copy(
                update={
                    "structured_output": None,
                    "capabilities_required": [],
                    "messages": [
                        GenerationMessageV1(role=GenerationMessageRole.USER, content="Hi")
                    ],
                }
            ),
            dry_run=True,
        )
        checks.append(("openai", openai_result.model_dump(by_alias=True, mode="json")))

    if adapter in {"local", "all"}:
        local_result = await service.generate(
            build_sample_request(provider_id="openai-compatible").model_copy(
                update={
                    "structured_output": None,
                    "capabilities_required": [],
                    "messages": [
                        GenerationMessageV1(role=GenerationMessageRole.USER, content="Hi")
                    ],
                }
            ),
            dry_run=True,
        )
        checks.append(("local", local_result.model_dump(by_alias=True, mode="json")))

    print(json.dumps({"checks": checks}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AEGIS provider harness")
    parser.add_argument(
        "--adapter", default="mock", choices=["mock", "recorded", "openai", "local", "all"]
    )
    args = parser.parse_args()
    return asyncio.run(run_harness(args.adapter))


if __name__ == "__main__":
    sys.exit(main())
