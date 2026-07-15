# Local OpenTelemetry stack for Phase 31.
#
# Services:
# - otel-collector : OTLP receiver (4317/4318), Prometheus exporter (:8889)
# - prometheus     : scrapes collector metrics
# - tempo          : trace backend
# - grafana        : dashboards (http://localhost:3001)
#
# Start with the main compose file (services are defined there) or:
#   docker compose up -d otel-collector prometheus tempo grafana
