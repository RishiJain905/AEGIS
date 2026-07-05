"""Deterministic request fingerprinting for recorded responses."""

from __future__ import annotations

import hashlib
import json

from aegis_contracts.generation import GenerationRequestV1, RecordedResponseKeyV1
from aegis_contracts.versioning import RECORDED_RESPONSE_KEY_SCHEMA_VERSION


def request_fingerprint(request: GenerationRequestV1) -> str:
    payload = {
        "providerId": request.model_config_ref.provider_id,
        "modelId": request.model_config_ref.model_id,
        "promptVersion": request.model_config_ref.prompt_version,
        "messages": [
            message.model_dump(by_alias=True, mode="json") for message in request.messages
        ],
        "structuredOutput": (
            request.structured_output.model_dump(by_alias=True, mode="json")
            if request.structured_output is not None
            else None
        ),
        "tools": [tool.model_dump(by_alias=True, mode="json") for tool in request.tools],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def recorded_response_key(request: GenerationRequestV1) -> RecordedResponseKeyV1:
    return RecordedResponseKeyV1(
        schema_version=RECORDED_RESPONSE_KEY_SCHEMA_VERSION,
        provider_id=request.model_config_ref.provider_id,
        model_id=request.model_config_ref.model_id,
        prompt_version=request.model_config_ref.prompt_version,
        request_hash=request_fingerprint(request),
    )
