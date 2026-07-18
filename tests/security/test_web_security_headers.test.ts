import { describe, expect, it } from 'vitest';

import nextConfig from '../../apps/web/next.config';

describe('web security headers', () => {
  it('applies the browser trust-boundary policy to every route', async () => {
    const routes = await nextConfig.headers?.();

    expect(routes).toHaveLength(1);
    expect(routes?.[0]?.source).toBe('/(.*)');

    const headers = Object.fromEntries(
      (routes?.[0]?.headers ?? []).map(({ key, value }) => [key, value]),
    );
    expect(headers['Content-Security-Policy']).toContain("default-src 'self'");
    expect(headers['Content-Security-Policy']).toContain("object-src 'none'");
    expect(headers['Content-Security-Policy']).toContain("frame-ancestors 'none'");
    expect(headers['Content-Security-Policy']).not.toContain("'unsafe-eval'");
    expect(headers['X-Content-Type-Options']).toBe('nosniff');
    expect(headers['Referrer-Policy']).toBe('strict-origin-when-cross-origin');
    expect(headers['Permissions-Policy']).toContain('camera=()');
    expect(headers['X-Frame-Options']).toBe('DENY');
    expect(nextConfig.poweredByHeader).toBe(false);
  });
});
