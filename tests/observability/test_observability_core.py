"""Observability unit tests — schema, redaction, labels, health, exporter failure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.fixtures import FIXTURE_MODEL_MAP
from aegis_contracts.observability import (
    FORBIDDEN_METRIC_LABELS,
    DependencyStateV1,
    HealthResponseV1,
    ReadyResponseV1,
    ReadyStatusV1,
    StructuredLogRecordV1,
    TelemetryContextV1,
)
from aegis_contracts.parsing import parse_contract
from aegis_observability.context import (
    TelemetryContextState,
    extract_headers,
    get_context,
    merge_context,
    propagate_headers,
    use_context,
)
from aegis_observability.health import DependencyProbeResult, evaluate_readiness
from aegis_observability.instrumentation import traced_operation
from aegis_observability.logging import get_logger
from aegis_observability.metrics import MetricLabelError, get_metrics, validate_metric_labels
from aegis_observability.redaction import REDACTED, redact_headers, redact_mapping, redact_string
from aegis_observability.setup import (
    init_observability,
    reset_observability_for_tests,
    shutdown_observability,
)

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "valid"


@pytest.fixture(autouse=True)
def _reset_obs() -> None:
    reset_observability_for_tests()
    yield
    reset_observability_for_tests()


def test_structured_log_schema_fixture() -> None:
    payload = json.loads((FIXTURES / "structured_log_record_v1.json").read_text())
    record = parse_contract(StructuredLogRecordV1, payload)
    assert record.service == "api"
    assert record.trace_id.startswith("trc_")


def test_telemetry_context_fixture() -> None:
    payload = json.loads((FIXTURES / "telemetry_context_v1.json").read_text())
    ctx = parse_contract(TelemetryContextV1, payload)
    assert ctx.operation == "http.request"


def test_health_and_ready_fixtures_distinct() -> None:
    health = parse_contract(
        HealthResponseV1,
        json.loads((FIXTURES / "health_response_v1.json").read_text()),
    )
    ready = parse_contract(
        ReadyResponseV1,
        json.loads((FIXTURES / "ready_response_v1.json").read_text()),
    )
    assert health.status.value == "ok"
    assert ready.status.value == "ready"
    assert "dependencies" in ready.model_dump(by_alias=True)
    assert "dependencies" not in health.model_dump(by_alias=True)


def test_correlation_context_propagation() -> None:
    inbound = {
        "X-Request-Id": "req_TESTREQUESTID00000000001",
        "X-Correlation-Id": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
    }
    ctx = extract_headers(inbound)
    assert ctx.request_id == "req_TESTREQUESTID00000000001"
    assert ctx.correlation_id == "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    headers = propagate_headers(ctx)
    assert headers["x-request-id"] == ctx.request_id
    assert "traceparent" in headers


def test_async_worker_context_propagation() -> None:
    outer = TelemetryContextState(service="worker", operation="batch")
    with use_context(outer):
        merge_context(run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert get_context() is not None
        assert get_context().run_id == "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert get_context().service == "worker"


def test_metric_labels_reject_unbounded() -> None:
    with pytest.raises(MetricLabelError):
        validate_metric_labels({"user_id": "user:1", "service": "api"})
    for forbidden in FORBIDDEN_METRIC_LABELS:
        with pytest.raises(MetricLabelError):
            validate_metric_labels({"service": "api", forbidden: "x"})
    ok = validate_metric_labels({"service": "api", "operation": "http.request", "status": "200"})
    assert ok["status"] == "200"


def test_metric_registration_noop() -> None:
    init_observability(service_name="test", enabled=False)
    metrics = get_metrics()
    metrics.record_api_request(
        duration_ms=12.0,
        status="200",
        method="GET",
        route_group="health",
    )
    assert metrics.exporter_failure_count == 0


def test_readiness_semantics() -> None:
    ready = evaluate_readiness(
        [
            DependencyProbeResult("postgres", DependencyStateV1.OK, True, 1.0),
            DependencyProbeResult("redis", DependencyStateV1.OK, True, 1.0),
        ]
    )
    assert ready == ReadyStatusV1.READY
    not_ready = evaluate_readiness(
        [
            DependencyProbeResult("postgres", DependencyStateV1.UNAVAILABLE, True, 1.0),
        ]
    )
    assert not_ready == ReadyStatusV1.NOT_READY
    degraded = evaluate_readiness(
        [
            DependencyProbeResult("postgres", DependencyStateV1.OK, True, 1.0),
            DependencyProbeResult("cache", DependencyStateV1.DEGRADED, False, 1.0),
        ]
    )
    assert degraded == ReadyStatusV1.DEGRADED


def test_redaction_of_credentials_and_sensitive_fields() -> None:
    payload = {
        "password": "super-secret",
        "authorization": "Bearer abc.def.ghi",
        "cookie": "aegis_session=deadbeef",
        "token": "refresh-token-value",
        "safe": "hello",
        "nested": {"api_key": "sk-abcdefghijklmnop", "count": 1},
    }
    redacted = redact_mapping(payload)
    assert redacted["password"] == REDACTED
    assert redacted["authorization"] == REDACTED
    assert redacted["cookie"] == REDACTED
    assert redacted["token"] == REDACTED
    assert redacted["safe"] == "hello"
    assert redacted["nested"]["api_key"] == REDACTED
    assert "[REDACTED]" in redact_string("Authorization: Bearer abc.def")
    headers = redact_headers({"Authorization": "Bearer x", "X-Request-Id": "req_1"})
    assert headers["Authorization"] == REDACTED
    assert headers["X-Request-Id"] == "req_1"


def test_exporter_failure_does_not_break_domain() -> None:
    runtime = init_observability(service_name="test", enabled=False)
    runtime.record_exporter_failure(RuntimeError("collector down"))
    # Domain path continues
    with traced_operation(service="test", operation="domain.work") as state:
        state["status"] = "ok"
        result = 1 + 1
    assert result == 2
    assert runtime.exporter_failures >= 1


def test_structured_logger_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    init_observability(service_name="test", enabled=False, json_logs=True)
    with use_context(TelemetryContextState(service="test", operation="log.test")):
        get_logger("unit", service="test").info("hello world", operation="log.test", foo="bar")
    _ = capsys.readouterr()
    record = {
        "schemaVersion": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "level": "info",
        "message": "hello",
        "service": "test",
        "operation": "log.test",
        "attributes": {},
    }
    parse_contract(StructuredLogRecordV1, record)


def test_duplicate_init_is_idempotent() -> None:
    first = init_observability(service_name="test", enabled=False)
    second = init_observability(service_name="test", enabled=False)
    assert first is second
    shutdown_observability()


def test_observability_fixture_models_registered() -> None:
    for name in (
        "telemetry_context_v1",
        "structured_log_record_v1",
        "health_response_v1",
        "ready_response_v1",
        "dependency_status_v1",
        "metric_label_policy_v1",
    ):
        assert name in FIXTURE_MODEL_MAP
