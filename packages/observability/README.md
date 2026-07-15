# observability

Structured logging, OpenTelemetry tracing/metrics, correlation context, redaction,
and bounded dependency health probes for AEGIS (Phase 31).

## Dependencies

- May depend on `aegis-contracts`.
- Must not import domain business logic from apps or services.
- OpenTelemetry exporters fail open: exporter errors are counted and logged, never raised into domain paths.

## Usage

```python
from aegis_observability import init_observability, get_logger, get_metrics

init_observability(service_name="aegis-api", otlp_endpoint="http://localhost:4317")
logger = get_logger("demo", service="aegis-api")
logger.info("hello", operation="demo")
```
