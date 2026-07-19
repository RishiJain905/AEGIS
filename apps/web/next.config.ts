import type { NextConfig } from 'next';

function origin(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

const connectSources = new Set(["'self'"]);
for (const value of [
  origin(process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'),
  origin(process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws/v1/realtime'),
]) {
  if (value) connectSources.add(value);
}

const scriptSources = ["'self'", "'unsafe-inline'"];
if (process.env.NODE_ENV === 'development') scriptSources.push("'unsafe-eval'");

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSources.join(' ')}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src ${[...connectSources].join(' ')}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

const securityHeaders = [
  { key: 'Content-Security-Policy', value: contentSecurityPolicy },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
  },
  { key: 'X-Frame-Options', value: 'DENY' },
];

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ['@aegis/ui'],
  headers() {
    return Promise.resolve([{ source: '/(.*)', headers: securityHeaders }]);
  },
};

export default nextConfig;
