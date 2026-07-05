"""Unit tests for provider redaction and cost estimation."""

from __future__ import annotations

from aegis_contracts.generation import ProviderUsageV1
from aegis_contracts.versioning import PROVIDER_USAGE_SCHEMA_VERSION
from aegis_model_provider.cost import estimate_cost_usd, with_estimated_cost
from aegis_model_provider.redaction import (
    contains_secret_material,
    redact_string,
    sanitize_request_payload,
)


def test_redact_api_key_patterns() -> None:
    redacted = redact_string("Authorization: Bearer sk-testsecretvalue123456")
    assert "sk-testsecretvalue123456" not in redacted
    assert "[REDACTED]" in redacted


def test_fixture_secret_detection() -> None:
    assert contains_secret_material("sk-abcdefghijklmnopqrstuvwxyz")


def test_sanitize_request_redacts_system_prompt() -> None:
    sanitized = sanitize_request_payload(
        {
            "messages": [
                {"role": "system", "content": "secret system"},
                {"role": "user", "content": "hello"},
            ]
        }
    )
    assert sanitized["messages"][0]["content"] == "[REDACTED]"


def test_cost_estimation_is_non_negative() -> None:
    usage = ProviderUsageV1(
        schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )
    estimated = with_estimated_cost(model_id="gpt-4o-mini", usage=usage)
    assert estimated.estimated_cost_usd is not None
    assert estimate_cost_usd(model_id="mock-v1", prompt_tokens=10, completion_tokens=5) == 0.0
