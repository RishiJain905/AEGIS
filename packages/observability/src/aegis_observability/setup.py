"""OpenTelemetry initialization with fail-open exporter behavior."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from aegis_observability.logging import StructuredLogger, configure_root_logging, get_logger
from aegis_observability.metrics import AegisMetrics, set_metrics

_LOCK = Lock()
_RUNTIME: ObservabilityRuntime | None = None
_INITIALIZED = False


@dataclass
class ObservabilityRuntime:
    service_name: str
    enabled: bool
    tracer_provider: Any | None
    meter_provider: Any | None
    metrics: AegisMetrics
    logger: StructuredLogger
    exporter_failures: int = 0

    def record_exporter_failure(self, error: Exception | None = None) -> None:
        self.exporter_failures += 1
        self.metrics.record_exporter_failure()
        self.logger.warning(
            "Telemetry exporter failure (non-fatal)",
            operation="otel.export",
            outcome="failure",
            error_kind=type(error).__name__ if error else "ExporterFailure",
        )


class _FailOpenSpanExporter:
    """Wraps an OTLP span exporter so failures never raise into domain code."""

    def __init__(self, inner: Any, runtime_getter: Any) -> None:
        self._inner = inner
        self._runtime_getter = runtime_getter

    def export(self, spans: Any) -> Any:
        try:
            return self._inner.export(spans)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            try:
                from opentelemetry.sdk.trace.export import SpanExportResult

                return SpanExportResult.FAILURE
            except Exception:  # noqa: BLE001
                return 1

    def shutdown(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._inner.shutdown(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            return None

    def force_flush(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._inner.force_flush(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            return False


class _FailOpenMetricExporter:
    def __init__(self, inner: Any, runtime_getter: Any) -> None:
        self._inner = inner
        self._runtime_getter = runtime_getter

    def export(self, metrics_data: Any, timeout_millis: float = 10_000, **kwargs: Any) -> Any:
        try:
            return self._inner.export(metrics_data, timeout_millis=timeout_millis, **kwargs)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            try:
                from opentelemetry.sdk.metrics.export import MetricExportResult

                return MetricExportResult.FAILURE
            except Exception:  # noqa: BLE001
                return 1

    def shutdown(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._inner.shutdown(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            return None

    def force_flush(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._inner.force_flush(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            runtime = self._runtime_getter()
            if runtime is not None:
                runtime.record_exporter_failure(exc)
            return False


def _get_runtime_unlocked() -> ObservabilityRuntime | None:
    return _RUNTIME


def init_observability(
    *,
    service_name: str,
    enabled: bool = True,
    otlp_endpoint: str = "http://localhost:4317",
    otlp_protocol: str = "grpc",
    sampler_arg: float = 1.0,
    metrics_export_interval_ms: int = 15000,
    log_level: str = "info",
    json_logs: bool = True,
    force: bool = False,
) -> ObservabilityRuntime:
    """Initialize OpenTelemetry providers. Safe to call multiple times (idempotent)."""
    global _RUNTIME, _INITIALIZED
    with _LOCK:
        if _INITIALIZED and not force and _RUNTIME is not None:
            return _RUNTIME

        configure_root_logging(level=log_level, json_logs=json_logs)
        logger = get_logger("aegis.observability", service=service_name, json_logs=json_logs)

        if not enabled:
            metrics = AegisMetrics(None, service=service_name)
            set_metrics(metrics)
            _RUNTIME = ObservabilityRuntime(
                service_name=service_name,
                enabled=False,
                tracer_provider=None,
                meter_provider=None,
                metrics=metrics,
                logger=logger,
            )
            _INITIALIZED = True
            logger.info(
                "Observability disabled; using noop metrics",
                operation="otel.init",
                outcome="success",
            )
            return _RUNTIME

        tracer_provider = None
        meter_provider = None
        meter: Any | None = None

        try:
            from opentelemetry import metrics as metrics_api
            from opentelemetry import trace
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

            resource = Resource.create({"service.name": service_name})
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=ParentBasedTraceIdRatio(sampler_arg),
            )

            # Protocol-specific exporters differ by type; construct via Any to keep
            # fail-open wrappers protocol-agnostic under mypy.
            otlp_span: Any
            otlp_metric: Any
            if otlp_protocol == "http/protobuf":
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                    OTLPMetricExporter as HttpMetricExporter,
                )
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HttpSpanExporter,
                )

                otlp_span = HttpSpanExporter(endpoint=otlp_endpoint)
                otlp_metric = HttpMetricExporter(endpoint=otlp_endpoint)
            else:
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                    OTLPMetricExporter as GrpcMetricExporter,
                )
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter as GrpcSpanExporter,
                )

                otlp_span = GrpcSpanExporter(endpoint=otlp_endpoint, insecure=True)
                otlp_metric = GrpcMetricExporter(endpoint=otlp_endpoint, insecure=True)

            span_exporter: Any = _FailOpenSpanExporter(otlp_span, _get_runtime_unlocked)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(tracer_provider)

            metric_exporter: Any = _FailOpenMetricExporter(
                otlp_metric,
                _get_runtime_unlocked,
            )
            reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=metrics_export_interval_ms,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics_api.set_meter_provider(meter_provider)
            meter = meter_provider.get_meter("aegis.observability")
        except Exception as exc:  # noqa: BLE001 — never block startup on OTel
            logger.warning(
                "OpenTelemetry initialization failed; continuing with noop exporters",
                operation="otel.init",
                outcome="failure",
                error_kind=type(exc).__name__,
            )
            meter = None
            tracer_provider = None
            meter_provider = None

        metrics = AegisMetrics(meter, service=service_name)
        set_metrics(metrics)
        _RUNTIME = ObservabilityRuntime(
            service_name=service_name,
            enabled=True,
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            metrics=metrics,
            logger=logger,
        )
        _INITIALIZED = True
        logger.info(
            "Observability initialized",
            operation="otel.init",
            outcome="success",
            endpoint=otlp_endpoint,
            protocol=otlp_protocol,
        )
        return _RUNTIME


def get_runtime() -> ObservabilityRuntime | None:
    with _LOCK:
        return _RUNTIME


def is_initialized() -> bool:
    with _LOCK:
        return _INITIALIZED


def shutdown_observability() -> None:
    global _RUNTIME, _INITIALIZED
    with _LOCK:
        runtime = _RUNTIME
        _RUNTIME = None
        _INITIALIZED = False
    if runtime is None:
        return
    for provider in (runtime.tracer_provider, runtime.meter_provider):
        if provider is None:
            continue
        try:
            provider.shutdown()
        except Exception as exc:  # noqa: BLE001
            runtime.record_exporter_failure(exc)


def reset_observability_for_tests() -> None:
    shutdown_observability()
    from aegis_observability.metrics import reset_metrics_for_tests

    reset_metrics_for_tests()
