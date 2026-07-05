"""Mock provider for deterministic CI and local development."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from aegis_contracts.generation import (
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderFinishReason,
    ProviderUsageV1,
)
from aegis_contracts.versioning import (
    GENERATION_RESPONSE_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
)

from aegis_model_provider.cost import with_estimated_cost
from aegis_model_provider.fingerprint import request_fingerprint
from aegis_model_provider.structured_output import validate_structured_output


class MockProvider:
    provider_id = "mock"

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[
                ProviderCapability.STRUCTURED_OUTPUT,
                ProviderCapability.TOOLS,
            ],
        )

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        fingerprint = request_fingerprint(request)
        user_text = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role.value == "user"
            ),
            "",
        )
        structured_data = None
        content = None
        prompt_version = request.model_config_ref.prompt_version
        if request.structured_output is not None:
            if prompt_version == "phase20-watchtower-v1":
                payload = {
                    "alertSummaries": [],
                    "groupedAlertIds": [],
                    "separatedAlertIds": [],
                    "correlationDecisions": [],
                    "escalation": "investigate",
                    "escalationRationale": f"Mock WATCHTOWER triage for request {fingerprint}",
                    "confidence": 0.78,
                    "evidenceCitations": [],
                    "toolRequests": [{"name": "list_alerts", "arguments": {}}],
                }
                structured_data = validate_structured_output(payload, request.structured_output)
                content = json.dumps(structured_data)
            elif prompt_version == "phase20-trace-v1":
                payload = {
                    "rationale": f"Mock TRACE investigation for request {fingerprint}",
                    "confidence": 0.81,
                    "evidenceCitations": [],
                    "toolRequests": [{"name": "search_events", "arguments": {"query": ""}}],
                    "seedAssetIds": [],
                    "maxHops": 3,
                    "maxToolCalls": 12,
                    "searchSteps": [
                        {
                            "toolName": "list_existing_evidence",
                            "arguments": {},
                            "purpose": "Review visible evidence",
                        }
                    ],
                    "candidateAssets": [],
                    "evidenceAttachments": [],
                    "graphHighlights": [],
                    "edgeHighlights": [],
                    "overlayRationale": "Mock bounded graph overlay",
                }
                structured_data = validate_structured_output(payload, request.structured_output)
                content = json.dumps(structured_data)
            elif "rationale" in (request.structured_output.json_schema.get("required") or []):
                payload = {
                    "rationale": f"Mock investigation step for request {fingerprint}",
                    "confidence": 0.82,
                    "evidenceCitations": [],
                    "toolRequests": [{"name": "list_evidence", "arguments": {}}],
                }
                structured_data = validate_structured_output(payload, request.structured_output)
                content = json.dumps(structured_data)
            elif "invalid" in user_text.lower():
                payload = {"summary": 123, "confidence": "high"}
                content = json.dumps(payload)
                structured_data = None
            else:
                payload = {
                    "summary": f"Mock analysis for request {fingerprint}",
                    "confidence": 0.82,
                }
                structured_data = validate_structured_output(payload, request.structured_output)
                content = json.dumps(structured_data)
        else:
            content = f"Mock completion for request {fingerprint}"

        usage = with_estimated_cost(
            model_id=request.model_config_ref.model_id,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=42,
                completion_tokens=18,
                total_tokens=60,
            ),
        )
        return GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_id=self.provider_id,
            model_id=request.model_config_ref.model_id,
            prompt_version=request.model_config_ref.prompt_version,
            content=content,
            structured_data=structured_data,
            finish_reason=ProviderFinishReason.STOP,
            usage=usage,
            latency_ms=12,
            completed_at=datetime.now(UTC),
        )
