/** Shared cookie-authenticated fetch helpers for Phase 30. */

import { apiErrorEnvelopeSchema, parseContract } from '@aegis/contracts-ts';

import { ApiClientError } from '@/lib/api/types';
import { applyCorrelationHeaders } from '@/lib/observability/correlation';

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
}

let memoryCsrfToken: string | null = null;

function getCsrfCookieName(): string {
  return process.env.NEXT_PUBLIC_AEGIS_CSRF_COOKIE_NAME ?? 'aegis_csrf';
}

function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') {
    return null;
  }
  const name = getCsrfCookieName();
  const prefix = `${name}=`;
  for (const part of document.cookie.split('; ')) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}

export function setMemoryCsrfToken(token: string | null): void {
  memoryCsrfToken = token;
}

export function getCsrfToken(): string | null {
  // Prefer the in-memory token from the current session response; fall back to
  // the non-httponly CSRF cookie (named by NEXT_PUBLIC_AEGIS_CSRF_COOKIE_NAME)
  // so requests still carry a token after a full page reload before the session
  // query rehydrates memory.
  return memoryCsrfToken ?? readCsrfCookie();
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrf = getCsrfToken();
    if (csrf) {
      headers.set('X-CSRF-Token', csrf);
    }
  }
  applyCorrelationHeaders(headers);
  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });
}

export async function apiFetchJson<T>(
  path: string,
  init: RequestInit = {},
  parser?: (data: unknown) => T,
): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    let envelope;
    try {
      const body: unknown = await response.json();
      envelope = parseContract(apiErrorEnvelopeSchema, body);
    } catch {
      throw new ApiClientError({
        code: 'HTTP_ERROR',
        message: `Request failed with status ${String(response.status)}`,
        status: response.status,
      });
    }
    throw new ApiClientError({
      code: envelope.code,
      message: envelope.message,
      status: response.status,
      traceId: envelope.traceId,
    });
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const data: unknown = await response.json();
  return parser ? parser(data) : (data as T);
}
