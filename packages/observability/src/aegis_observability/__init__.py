"""AEGIS observability — OpenTelemetry setup, structured logging, health, redaction."""

from __future__ import annotations

from aegis_observability.context import (
    TelemetryContextState,
    bind_context,
    clear_context,
    extract_headers,
    get_context,
    merge_context,
    propagate_headers,
    use_context,
)
from aegis_observability.health import (
    DependencyProbeResult,
    check_object_storage,
    check_postgres_bounded,
    check_redis_bounded,
    evaluate_readiness,
)
from aegis_observability.instrumentation import (
    record_agent_task,
    record_approval_wait,
    record_provider_call,
    record_replay,
    record_scoring,
    record_simulation_events,
    traced_operation,
)
from aegis_observability.logging import StructuredLogger, get_logger
from aegis_observability.metrics import (
    AegisMetrics,
    get_metrics,
    reset_metrics_for_tests,
    validate_metric_labels,
)
from aegis_observability.redaction import (
    REDACTED,
    contains_sensitive_material,
    redact_headers,
    redact_mapping,
    redact_string,
    redact_value,
)
from aegis_observability.setup import (
    ObservabilityRuntime,
    get_runtime,
    init_observability,
    is_initialized,
    reset_observability_for_tests,
    shutdown_observability,
)

WORKSPACE_VERSION = "0.0.0-phase31"

__all__ = [
    "WORKSPACE_VERSION",
    "AegisMetrics",
    "DependencyProbeResult",
    "ObservabilityRuntime",
    "REDACTED",
    "StructuredLogger",
    "TelemetryContextState",
    "bind_context",
    "check_object_storage",
    "check_postgres_bounded",
    "check_redis_bounded",
    "clear_context",
    "contains_sensitive_material",
    "evaluate_readiness",
    "extract_headers",
    "get_context",
    "get_logger",
    "get_metrics",
    "get_runtime",
    "init_observability",
    "is_initialized",
    "merge_context",
    "propagate_headers",
    "record_agent_task",
    "record_approval_wait",
    "record_provider_call",
    "record_replay",
    "record_scoring",
    "record_simulation_events",
    "redact_headers",
    "redact_mapping",
    "redact_string",
    "redact_value",
    "reset_metrics_for_tests",
    "reset_observability_for_tests",
    "shutdown_observability",
    "traced_operation",
    "use_context",
    "validate_metric_labels",
]
