/** Frontend correlation-context helpers for Phase 31 observability. */

const REQUEST_ID_HEADER = 'X-Request-Id';
const CORRELATION_ID_HEADER = 'X-Correlation-Id';
const TRACEPARENT_HEADER = 'traceparent';
const RUN_ID_HEADER = 'X-Aegis-Run-Id';
const INCIDENT_ID_HEADER = 'X-Aegis-Incident-Id';

export type FrontendTelemetryContext = {
  requestId: string;
  correlationId: string;
  traceId: string;
  spanId: string;
  runId?: string;
  incidentId?: string;
};

function randomHex(bytes: number): string {
  const array = new Uint8Array(bytes);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
}

function toTraceId(): string {
  // Domain-compatible trc_ prefix with hex body.
  return `trc_${randomHex(13).toUpperCase()}`;
}

function toRequestId(): string {
  return `req_${randomHex(13).toUpperCase()}`;
}

let activeContext: FrontendTelemetryContext | null = null;

export function createTelemetryContext(
  overrides: Partial<FrontendTelemetryContext> = {},
): FrontendTelemetryContext {
  const traceId = overrides.traceId ?? toTraceId();
  const ctx: FrontendTelemetryContext = {
    requestId: overrides.requestId ?? toRequestId(),
    correlationId: overrides.correlationId ?? traceId,
    traceId,
    spanId: overrides.spanId ?? randomHex(8),
    runId: overrides.runId,
    incidentId: overrides.incidentId,
  };
  activeContext = ctx;
  return ctx;
}

export function getTelemetryContext(): FrontendTelemetryContext | null {
  return activeContext;
}

export function bindTelemetryContext(ctx: FrontendTelemetryContext): void {
  activeContext = ctx;
}

export function clearTelemetryContext(): void {
  activeContext = null;
}

export function toPropagationHeaders(
  ctx: FrontendTelemetryContext = createTelemetryContext(),
): Record<string, string> {
  const hexTrace = ctx.traceId
    .replace(/[^a-fA-F0-9]/g, '')
    .slice(-32)
    .padStart(32, '0')
    .toLowerCase();
  const hexSpan = ctx.spanId
    .replace(/[^a-fA-F0-9]/g, '')
    .slice(-16)
    .padStart(16, '0')
    .toLowerCase();
  const headers: Record<string, string> = {
    [TRACEPARENT_HEADER]: `00-${hexTrace}-${hexSpan}-01`,
    [REQUEST_ID_HEADER]: ctx.requestId,
    [CORRELATION_ID_HEADER]: ctx.correlationId,
  };
  if (ctx.runId) {
    headers[RUN_ID_HEADER] = ctx.runId;
  }
  if (ctx.incidentId) {
    headers[INCIDENT_ID_HEADER] = ctx.incidentId;
  }
  return headers;
}

export function applyCorrelationHeaders(
  headers: Headers,
  ctx?: FrontendTelemetryContext | null,
): Headers {
  const active = ctx ?? activeContext ?? createTelemetryContext();
  const values = toPropagationHeaders(active);
  for (const [key, value] of Object.entries(values)) {
    if (!headers.has(key)) {
      headers.set(key, value);
    }
  }
  return headers;
}

/** Never put secrets into browser telemetry helpers. */
export const SENSITIVE_BROWSER_KEYS = [
  'authorization',
  'cookie',
  'password',
  'token',
  'csrf',
  'session',
] as const;
