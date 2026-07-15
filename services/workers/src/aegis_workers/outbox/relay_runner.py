"""Outbox relay worker loop."""

from __future__ import annotations

import asyncio
import logging
import signal

from aegis_contracts import AegisSettings, load_settings
from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.metrics import GLOBAL_METRICS
from aegis_event_streaming.redis_client import create_redis_client
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker

logger = logging.getLogger(__name__)


async def run_outbox_relay(settings: AegisSettings | None = None) -> None:
    resolved = settings or load_settings()
    try:
        from aegis_observability.setup import init_observability

        init_observability(
            service_name=getattr(resolved, "OTEL_SERVICE_NAME", "aegis-worker"),
            enabled=getattr(resolved, "OTEL_ENABLED", True),
            otlp_endpoint=getattr(
                resolved, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            ),
            otlp_protocol=getattr(resolved, "OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"),
            log_level=resolved.LOG_LEVEL.value,
            json_logs=getattr(resolved, "AEGIS_LOG_JSON", True),
        )
    except Exception:  # noqa: BLE001
        pass
    config = StreamingConfig.from_env()
    engine = create_engine(resolved)
    session_maker = get_session_maker(resolved, engine=engine)
    redis = create_redis_client(resolved)
    relay = PostgresOutboxRelay(
        session_maker,
        redis,
        config=config,
        metrics=GLOBAL_METRICS,
    )

    stop_event = asyncio.Event()

    def handle_signal() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    logger.info("Outbox relay started", extra={"claimOwner": relay._claim_owner})
    try:
        while not stop_event.is_set():
            try:
                from aegis_observability.context import TelemetryContextState, use_context

                ctx = TelemetryContextState(
                    service="worker",
                    operation="outbox.relay.publish_batch",
                )
                with use_context(ctx):
                    published = await relay.publish_batch()
            except Exception:
                published = await relay.publish_batch()
            if published:
                logger.info("Published outbox batch", extra={"count": published})
                try:
                    from aegis_observability.metrics import get_metrics, validate_metric_labels

                    snap = GLOBAL_METRICS.snapshot()
                    labels = validate_metric_labels(
                        {"service": "worker", "operation": "outbox.relay", "status": "ok"}
                    )
                    get_metrics().outbox_unpublished.add(
                        int(snap.get("outboxUnpublished") or 0), labels
                    )
                except Exception:  # noqa: BLE001
                    pass
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=config.outbox_poll_interval_seconds,
                )
            except TimeoutError:
                continue
    finally:
        await redis.aclose()
        await dispose_engine(engine)
        logger.info("Outbox relay stopped")
        try:
            from aegis_observability.setup import shutdown_observability

            shutdown_observability()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run_outbox_relay())
