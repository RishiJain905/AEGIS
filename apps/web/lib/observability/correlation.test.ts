import { describe, expect, it } from 'vitest';

import {
  applyCorrelationHeaders,
  createTelemetryContext,
  SENSITIVE_BROWSER_KEYS,
  toPropagationHeaders,
} from '@/lib/observability/correlation';

describe('frontend correlation context', () => {
  it('creates domain-compatible request and trace identifiers', () => {
    const ctx = createTelemetryContext();
    expect(ctx.requestId.startsWith('req_')).toBe(true);
    expect(ctx.traceId.startsWith('trc_')).toBe(true);
    expect(ctx.correlationId).toBe(ctx.traceId);
  });

  it('emits W3C traceparent and request headers without secrets', () => {
    const ctx = createTelemetryContext({ runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV' });
    const headers = toPropagationHeaders(ctx);
    expect(headers.traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
    expect(headers['X-Request-Id']).toBe(ctx.requestId);
    expect(headers['X-Correlation-Id']).toBe(ctx.correlationId);
    expect(headers['X-Aegis-Run-Id']).toBe(ctx.runId);
    for (const key of SENSITIVE_BROWSER_KEYS) {
      expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain(key);
    }
  });

  it('applies correlation headers onto fetch Headers', () => {
    const headers = new Headers({ Accept: 'application/json' });
    applyCorrelationHeaders(headers);
    expect(headers.get('X-Request-Id')).toBeTruthy();
    expect(headers.get('traceparent')).toBeTruthy();
  });
});
