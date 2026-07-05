"""Recorded-response provider for deterministic replay."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_contracts.generation import (
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
)
from aegis_contracts.parsing import parse_contract
from aegis_contracts.versioning import (
    GENERATION_RESPONSE_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
)

from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.fingerprint import recorded_response_key
from aegis_model_provider.redaction import contains_secret_material


class RecordedResponseProvider:
    provider_id = "recorded"

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self._index = self._load_index()

    def _load_index(self) -> dict[str, Path]:
        manifest_path = self._fixtures_dir / "manifest.json"
        if not manifest_path.exists():
            return {}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        fixtures = manifest.get("fixtures", [])
        index: dict[str, Path] = {}
        for entry in fixtures:
            if not isinstance(entry, dict):
                continue
            key = entry.get("requestHash")
            relative = entry.get("path")
            if isinstance(key, str) and isinstance(relative, str):
                index[key] = self._fixtures_dir / relative
        return index

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[
                ProviderCapability.STRUCTURED_OUTPUT,
                ProviderCapability.TOOLS,
            ],
        )

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        key = recorded_response_key(request)
        fixture_path = self._index.get(key.request_hash)
        if fixture_path is None or not fixture_path.exists():
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message="Recorded response fixture not found",
                    details=key.model_dump(by_alias=True, mode="json"),
                    trace_id=request.trace_id,
                )
            )
        raw_text = fixture_path.read_text(encoding="utf-8")
        if contains_secret_material(raw_text):
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message="Recorded fixture contains forbidden secret material",
                    trace_id=request.trace_id,
                )
            )
        payload = json.loads(raw_text)
        response_payload = payload.get("response", payload)
        response = parse_contract(GenerationResponseV1, response_payload)
        return response.model_copy(
            update={
                "schema_version": GENERATION_RESPONSE_SCHEMA_VERSION,
                "request_id": request.request_id,
                "trace_id": request.trace_id,
                "provider_id": self.provider_id,
            }
        )
