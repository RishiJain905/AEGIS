"""WebSocket gateway metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class GatewayMetrics:
    active_connections: int = 0
    total_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    delivery_lag_ms: float = 0.0
    queue_depth_total: int = 0
    gaps_detected: int = 0
    resyncs_total: int = 0
    duplicates_suppressed: int = 0
    slow_clients: int = 0
    close_reasons: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def snapshot(self) -> dict[str, int | float | dict[str, int]]:
        with self._lock:
            return {
                "activeConnections": self.active_connections,
                "totalConnections": self.total_connections,
                "messagesSent": self.messages_sent,
                "messagesReceived": self.messages_received,
                "deliveryLagMs": self.delivery_lag_ms,
                "queueDepthTotal": self.queue_depth_total,
                "gapsDetected": self.gaps_detected,
                "resyncsTotal": self.resyncs_total,
                "duplicatesSuppressed": self.duplicates_suppressed,
                "slowClients": self.slow_clients,
                "closeReasons": dict(self.close_reasons),
            }

    def connection_opened(self) -> None:
        with self._lock:
            self.active_connections += 1
            self.total_connections += 1
        try:
            from aegis_observability.metrics import get_metrics, validate_metric_labels

            get_metrics().ws_connections.add(
                1,
                validate_metric_labels(
                    {
                        "service": "api",
                        "operation": "ws.connect",
                        "ws_event": "connect",
                        "status": "ok",
                    }
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    def connection_closed(self, reason: str) -> None:
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)
            self.close_reasons[reason] = self.close_reasons.get(reason, 0) + 1
        try:
            from aegis_observability.metrics import get_metrics, validate_metric_labels

            get_metrics().ws_connections.add(
                -1,
                validate_metric_labels(
                    {
                        "service": "api",
                        "operation": "ws.disconnect",
                        "ws_event": "disconnect",
                        "status": "ok",
                    }
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    def record_sent(self) -> None:
        with self._lock:
            self.messages_sent += 1
        try:
            from aegis_observability.metrics import get_metrics, validate_metric_labels

            get_metrics().ws_messages.add(
                1,
                validate_metric_labels(
                    {
                        "service": "api",
                        "operation": "ws.message",
                        "ws_event": "send",
                        "status": "ok",
                    }
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    def record_received(self) -> None:
        with self._lock:
            self.messages_received += 1
        try:
            from aegis_observability.metrics import get_metrics, validate_metric_labels

            get_metrics().ws_messages.add(
                1,
                validate_metric_labels(
                    {
                        "service": "api",
                        "operation": "ws.message",
                        "ws_event": "receive",
                        "status": "ok",
                    }
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    def record_gap(self) -> None:
        with self._lock:
            self.gaps_detected += 1

    def record_resync(self) -> None:
        with self._lock:
            self.resyncs_total += 1

    def record_duplicate(self) -> None:
        with self._lock:
            self.duplicates_suppressed += 1

    def record_slow_client(self) -> None:
        with self._lock:
            self.slow_clients += 1

    def update_queue_depth(self, depth: int) -> None:
        with self._lock:
            self.queue_depth_total = depth


GLOBAL_GATEWAY_METRICS = GatewayMetrics()
