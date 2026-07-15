export {
  applyCorrelationHeaders,
  bindTelemetryContext,
  clearTelemetryContext,
  createTelemetryContext,
  getTelemetryContext,
  SENSITIVE_BROWSER_KEYS,
  toPropagationHeaders,
  type FrontendTelemetryContext,
} from '@/lib/observability/correlation';
