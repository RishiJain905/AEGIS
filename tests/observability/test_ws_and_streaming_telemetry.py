"""WebSocket and streaming metric bridge tests."""

from __future__ import annotations

from aegis_api.websocket.metrics import GatewayMetrics
from aegis_event_streaming.metrics import StreamingMetrics
from aegis_observability.metrics import get_metrics
from aegis_observability.setup import init_observability, reset_observability_for_tests


def setup_function() -> None:
    reset_observability_for_tests()
    init_observability(service_name="api", enabled=False)


def teardown_function() -> None:
    reset_observability_for_tests()


def test_websocket_metrics_emit_otel_counters() -> None:
    metrics = GatewayMetrics()
    before = get_metrics().exporter_failure_count
    metrics.connection_opened()
    metrics.record_received()
    metrics.record_sent()
    metrics.connection_closed("client")
    assert metrics.snapshot()["totalConnections"] == 1
    assert get_metrics().exporter_failure_count == before


def test_streaming_metrics_snapshot_stable() -> None:
    streaming = StreamingMetrics()
    streaming.record_publish(latency_ms=5.0)
    streaming.update_outbox_stats(unpublished=2, oldest_age_seconds=1.5)
    snap = streaming.snapshot()
    assert snap["publishesTotal"] == 1
    assert snap["outboxUnpublished"] == 2
