import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { terminalTaskStatus, useSendAgentMessage } from './use-agent-chat';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

function jsonResponse(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('terminalTaskStatus', () => {
  it('reads status from a task-create response', () => {
    expect(terminalTaskStatus({ status: 'failed' })).toBe('failed');
  });
  it('reads the newest task status from a session-detail response', () => {
    expect(
      terminalTaskStatus({ tasks: [{ status: 'completed' }, { status: 'timed_out' }] }),
    ).toBe('timed_out');
  });
  it('returns null when no status is present', () => {
    expect(terminalTaskStatus({})).toBeNull();
    expect(terminalTaskStatus(null)).toBeNull();
  });
});

describe('useSendAgentMessage auto-retry', () => {
  it('retries exactly once when the first task fails, then stops', async () => {
    apiFetch
      .mockResolvedValueOnce(jsonResponse({ status: 'failed' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'completed' }));

    const { result } = renderHook(() => useSendAgentMessage('run_x'), { wrapper });
    await result.current.mutateAsync({
      role: 'WATCHTOWER',
      instructions: 'Sweep alerts',
      sessionId: 'agent-session:s1',
    });

    // Exactly two sends: the original and one retry.
    expect(apiFetch).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(result.current.isRetrying).toBe(false);
    });
  });

  it('does not retry when the first task succeeds', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ status: 'completed' }));
    const { result } = renderHook(() => useSendAgentMessage('run_x'), { wrapper });
    await result.current.mutateAsync({
      role: 'TRACE',
      instructions: 'Investigate host',
      sessionId: 'agent-session:s1',
    });
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it('retries at most once even if the retry also fails (stays honest)', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ status: 'failed' }));
    const { result } = renderHook(() => useSendAgentMessage('run_x'), { wrapper });
    await result.current.mutateAsync({
      role: 'ORACLE',
      instructions: 'Weigh explanations',
      sessionId: 'agent-session:s1',
    });
    // Original + one retry; no infinite loop.
    expect(apiFetch).toHaveBeenCalledTimes(2);
  });
});
