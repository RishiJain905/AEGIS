import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { queryKeys } from '@/lib/api/query-keys';

import { AgentChatPanel } from './agent-chat-panel';

const apiFetch = vi.fn();
vi.mock('@/lib/api/auth-fetch', () => ({
  apiFetch: (path: string, init?: RequestInit) => apiFetch(path, init) as unknown,
}));

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const TRACE = 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function watchtowerSessionDetail(overrides: { taskStatus?: string; withError?: boolean } = {}) {
  const taskStatus = overrides.taskStatus ?? 'completed';
  return {
    schemaVersion: 1,
    session: {
      schemaVersion: 1,
      id: 'agent-session:ags_chat_001',
      runId: RUN_ID,
      incidentId: null,
      role: 'WATCHTOWER',
      state: 'verifying',
      traceId: TRACE,
      createdAt: '2026-07-22T00:00:00.000Z',
      updatedAt: '2026-07-22T00:00:00.000Z',
    },
    tasks: [
      {
        schemaVersion: 1,
        id: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        sessionId: 'agent-session:ags_chat_001',
        runId: RUN_ID,
        incidentId: null,
        status: taskStatus,
        attempt: 1,
        idempotencyKey: 'chat-1',
        traceId: TRACE,
        providerId: 'openai-compatible',
        instructions: 'Sweep the current alerts',
        errorCode: overrides.withError ? 'PROVIDER_FAILURE' : null,
        errorMessage: overrides.withError ? 'Model timed out' : null,
        createdAt: '2026-07-22T00:00:00.000Z',
        updatedAt: '2026-07-22T00:00:01.000Z',
      },
    ],
    transitions: [],
    toolInvocations: [
      {
        schemaVersion: 1,
        id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        taskId: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        sessionId: 'agent-session:ags_chat_001',
        toolName: 'list_alerts',
        toolClass: 'read',
        status: 'success',
        durationMs: 12,
        input: {},
        output: {},
        errorCode: null,
        errorMessage: null,
        createdAt: '2026-07-22T00:00:00.500Z',
      },
    ],
    artifacts: [
      {
        schemaVersion: 1,
        id: 'aaf_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        taskId: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        sessionId: 'agent-session:ags_chat_001',
        artifactType: 'step_result',
        payload: {
          rationale: 'The identity provider shows anomalous auth.',
          confidence: 0.82,
          evidenceCitations: [{ evidenceId: 'evidence:evd_001', rationale: 'auth spike' }],
          toolRequests: [],
        },
        generationArtifactId: null,
        createdAt: '2026-07-22T00:00:01.000Z',
      },
    ],
    budget: null,
  };
}

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <AgentChatPanel runId={RUN_ID} />
    </QueryClientProvider>,
  );
  return { client, ...view };
}

describe('AgentChatPanel', () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it('restores a WATCHTOWER thread: operator bubble, tool chip, artifact and evidence', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ sessions: [watchtowerSessionDetail()] }));

    renderPanel();

    const panel = await screen.findByTestId('agent-chat-panel');
    expect(await within(panel).findByText('Sweep the current alerts')).toBeInTheDocument();
    expect(
      within(panel).getByText('The identity provider shows anomalous auth.'),
    ).toBeInTheDocument();
    expect(within(panel).getByText('list_alerts')).toBeInTheDocument();
    expect(within(panel).getByText('evidence:evd_001')).toBeInTheDocument();
  });

  it('asks only for operator-origin sessions', async () => {
    // The autonomy worker opens its own run-scoped WATCHTOWER sessions for background
    // triage. Without this filter the copilot rendered those as the operator's own
    // conversation — threads nobody started, stuck on "Working…" — and, worse, sent
    // follow-up messages into the newest one, which was usually an autonomy session.
    apiFetch.mockResolvedValue(jsonResponse({ sessions: [watchtowerSessionDetail()] }));

    renderPanel();
    await screen.findByTestId('agent-chat-panel');

    await waitFor(() => {
      const getCall = apiFetch.mock.calls.find(
        ([, init]) => ((init as RequestInit | undefined)?.method ?? 'GET') === 'GET',
      );
      expect(getCall?.[0]).toBe(`/api/v1/runs/${RUN_ID}/agent-sessions?origin=operator`);
    });
  });

  it('renders a failed turn honestly', async () => {
    apiFetch.mockResolvedValue(
      jsonResponse({
        sessions: [watchtowerSessionDetail({ taskStatus: 'failed', withError: true })],
      }),
    );

    renderPanel();

    const panel = await screen.findByTestId('agent-chat-panel');
    expect(await within(panel).findByText(/Model timed out/)).toBeInTheDocument();
    expect(within(panel).getByText(/PROVIDER_FAILURE/)).toBeInTheDocument();
  });

  it('creates a run-scoped session when sending the first message', async () => {
    // Initial list load is empty, then POST create, then the refetch.
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ sessions: [] }));
      }
      return Promise.resolve(jsonResponse(watchtowerSessionDetail()));
    });

    renderPanel();
    await screen.findByTestId('agent-chat-panel');

    const composer = screen.getByLabelText(/Message to WATCHTOWER/);
    await userEvent.type(composer, 'Sweep the run now');
    await userEvent.click(screen.getByRole('button', { name: /Send to WATCHTOWER/ }));

    await waitFor(() => {
      const postCall = apiFetch.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      );
      expect(postCall).toBeTruthy();
      expect(postCall?.[0]).toBe(`/api/v1/runs/${RUN_ID}/agent-sessions`);
      const body = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
        role?: string;
        instructions?: string;
        enqueueInitialTask?: boolean;
      };
      expect(body.role).toBe('WATCHTOWER');
      expect(body.instructions).toBe('Sweep the run now');
      expect(body.enqueueInitialTask).toBe(true);
    });
  });

  it('resolves a still-running turn to its artifact via the poll refetch', async () => {
    // First list load: the task is still running (renders "Working…"). The poll refetch
    // then returns the completed turn, which must replace the working state — the panel
    // must never stay stuck on "Working…" once the backend reaches a terminal state.
    let calls = 0;
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        calls += 1;
        const status = calls >= 2 ? 'completed' : 'running';
        return Promise.resolve(
          jsonResponse({ sessions: [watchtowerSessionDetail({ taskStatus: status })] }),
        );
      }
      return Promise.resolve(jsonResponse(watchtowerSessionDetail()));
    });

    renderPanel();
    const panel = await screen.findByTestId('agent-chat-panel');
    expect(await within(panel).findByText('Working…')).toBeInTheDocument();

    // The poll interval (2500ms) drives the refetch that surfaces the completed turn.
    await waitFor(
      () =>
        expect(
          within(panel).getByText('The identity provider shows anomalous auth.'),
        ).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(within(panel).queryByText('Working…')).not.toBeInTheDocument();
  });

  it('sends a follow-up as a task on the existing role session', async () => {
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ sessions: [watchtowerSessionDetail()] }));
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });

    renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await screen.findByText('Sweep the current alerts');

    const composer = screen.getByLabelText(/Message to WATCHTOWER/);
    await userEvent.type(composer, 'Now check the file server');
    await userEvent.click(screen.getByRole('button', { name: /Send to WATCHTOWER/ }));

    await waitFor(() => {
      const postCall = apiFetch.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      );
      expect(postCall?.[0]).toBe('/api/v1/agent-sessions/agent-session:ags_chat_001/tasks');
      const body = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
        instructions?: string;
      };
      expect(body.instructions).toBe('Now check the file server');
    });
  });

  it('does not double-render the submission when a realtime refetch lands mid-flight', async () => {
    // The live-run-provider's `agent.*` event handler invalidates the session list the
    // moment the backend creates the task - well before this (inline, potentially slow)
    // POST resolves. That can land the real "Working…" turn while the mutation is still
    // pending. The panel must show the submission once, not twice, and the composer must
    // already be empty (it clears on send, not on response).
    let getCalls = 0;
    let resolvePost!: (value: Response) => void;
    const postPromise = new Promise<Response>((resolve) => {
      resolvePost = resolve;
    });

    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        getCalls += 1;
        // First load: no sessions yet. Second (simulated realtime-triggered) refetch: the
        // task already exists and is running, echoing the submitted instructions - as it
        // would once the backend has committed the row but before the LLM call finishes.
        const sessions =
          getCalls === 1
            ? []
            : [watchtowerSessionDetail({ taskStatus: 'running' })].map((detail) => ({
                ...detail,
                tasks: [{ ...detail.tasks[0], instructions: 'Sweep the run now' }],
              }));
        return Promise.resolve(jsonResponse({ sessions }));
      }
      return postPromise;
    });

    const { client } = renderPanel();
    await screen.findByTestId('agent-chat-panel');

    const composer = screen.getByLabelText<HTMLTextAreaElement>(/Message to WATCHTOWER/);
    await userEvent.type(composer, 'Sweep the run now');
    await userEvent.click(screen.getByRole('button', { name: /Send to WATCHTOWER/ }));

    // Composer clears immediately on send, not on response.
    await waitFor(() => {
      expect(composer.value).toBe('');
    });
    expect(await screen.findByRole('button', { name: /Sending…/ })).toBeInTheDocument();

    // Simulate the realtime handler's invalidation landing while the POST is still pending.
    await client.invalidateQueries({ queryKey: queryKeys.agentSessions.listForRun(RUN_ID) });

    const panel = screen.getByTestId('agent-chat-panel');
    await waitFor(() => {
      expect(within(panel).getAllByText('Sweep the run now')).toHaveLength(1);
    });
    // The real turn (now visible via the simulated refetch) shows its own "Working…" -
    // the optimistic placeholder's working indicator (a distinct testid, separate from the
    // sr-only aria-live announcement that legitimately always echoes the same words) must
    // not also be showing.
    expect(within(panel).getByText('Working…')).toBeInTheDocument();
    expect(within(panel).queryByTestId('agent-chat-working')).not.toBeInTheDocument();
    expect(within(panel).queryByTestId('agent-chat-retrying')).not.toBeInTheDocument();

    resolvePost(jsonResponse({ ok: true }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Send to WATCHTOWER/ })).toBeInTheDocument();
    });
  });
});
