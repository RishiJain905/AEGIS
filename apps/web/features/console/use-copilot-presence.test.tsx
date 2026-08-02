import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useRunAgentSessions } = vi.hoisted(() => ({
  useRunAgentSessions: vi.fn(),
}));

vi.mock('@/features/agent-chat/use-agent-chat', () => ({
  CHAT_ROLES: ['WATCHTOWER', 'TRACE', 'ORACLE', 'BASTION'] as const,
  useRunAgentSessions,
}));

import { useCopilotPresence } from './use-copilot-presence';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

interface DetailOptions {
  role?: string;
  taskId?: string;
  status?: string;
  rationale?: string;
  errorMessage?: string | null;
}

function detail({
  role = 'WATCHTOWER',
  taskId = 'atk_1',
  status = 'running',
  rationale,
  errorMessage = null,
}: DetailOptions = {}) {
  return {
    session: { id: `agent-session:${role}`, role },
    tasks: [
      {
        id: taskId,
        status,
        errorCode: errorMessage ? 'PROVIDER_FAILURE' : null,
        errorMessage,
        instructions: 'Sweep',
        createdAt: new Date().toISOString(),
        startedAt: null,
        traceId: null,
      },
    ],
    artifacts: rationale
      ? [{ artifactType: 'step_result', taskId, payload: { rationale } }]
      : [],
    toolInvocations: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('useCopilotPresence', () => {
  it('reports working roles from the authoritative task rows', () => {
    useRunAgentSessions.mockReturnValue({ data: [detail({ status: 'running' })] });
    const { result } = renderHook(() => useCopilotPresence(RUN_ID));
    expect(result.current.phase).toBe('working');
    expect(result.current.workingRoles).toEqual(['WATCHTOWER']);
  });

  it('treats history first seen already-terminal as read, not news', () => {
    useRunAgentSessions.mockReturnValue({
      data: [detail({ status: 'completed', rationale: 'Old reply.' })],
    });
    const { result } = renderHook(() => useCopilotPresence(RUN_ID));
    expect(result.current.phase).toBe('idle');
    expect(result.current.unreadCount).toBe(0);
  });

  it('turns an in-flight → completed transition into a persistent unread with a preview', () => {
    useRunAgentSessions.mockReturnValue({ data: [detail({ status: 'running' })] });
    const { result, rerender } = renderHook(() => useCopilotPresence(RUN_ID));

    useRunAgentSessions.mockReturnValue({
      data: [
        detail({
          status: 'completed',
          rationale: 'The identity provider shows anomalous auth. More detail follows.',
        }),
      ],
    });
    rerender();

    expect(result.current.phase).toBe('unread');
    expect(result.current.unreadCount).toBe(1);
    expect(result.current.preview).toBe('The identity provider shows anomalous auth.');
    expect(result.current.previewRole).toBe('WATCHTOWER');
    expect(result.current.announcement).toBe('WATCHTOWER replied');

    // The unread persists across further refetches until the sheet opens.
    rerender();
    expect(result.current.unreadCount).toBe(1);
  });

  it('marks failures and previews the error first line', () => {
    useRunAgentSessions.mockReturnValue({ data: [detail({ status: 'running' })] });
    const { result, rerender } = renderHook(() => useCopilotPresence(RUN_ID));

    useRunAgentSessions.mockReturnValue({
      data: [detail({ status: 'failed', errorMessage: 'Model timed out\nstack…' })],
    });
    rerender();

    expect(result.current.phase).toBe('failed');
    expect(result.current.hasFailure).toBe(true);
    expect(result.current.preview).toBe('Model timed out');
    expect(result.current.announcement).toBe('WATCHTOWER needs attention');
  });

  it('clears unread the moment the sheet opens', () => {
    useRunAgentSessions.mockReturnValue({ data: [detail({ status: 'running' })] });
    const { result, rerender } = renderHook(() => useCopilotPresence(RUN_ID));

    useRunAgentSessions.mockReturnValue({
      data: [detail({ status: 'completed', rationale: 'Done.' })],
    });
    rerender();
    expect(result.current.unreadCount).toBe(1);

    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    expect(result.current.unreadCount).toBe(0);
    expect(result.current.phase).toBe('idle');
  });

  it('does not accrue unread while the operator is watching the sheet', () => {
    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    useRunAgentSessions.mockReturnValue({ data: [detail({ status: 'running' })] });
    const { result, rerender } = renderHook(() => useCopilotPresence(RUN_ID));

    useRunAgentSessions.mockReturnValue({
      data: [detail({ status: 'completed', rationale: 'Watched live.' })],
    });
    rerender();
    expect(result.current.unreadCount).toBe(0);
  });
});
