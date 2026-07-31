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

// The panel checks BASTION's incident prerequisite through the incidents feature, which
// needs an ApiClientProvider. These tests are about the task lifecycle, so stub it with a
// run that already has an open case (no BASTION gate) unless a test says otherwise.
const runIncidents = vi.fn((_runId: string) => ({
  isSuccess: true,
  data: [{ id: 'incident:inc_001' }],
}));
vi.mock('@/features/incidents', () => ({
  useRunIncidents: (runId: string) => runIncidents(runId) as unknown,
}));

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const TRACE = 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV';

interface SessionOverrides {
  taskStatus?: string;
  withError?: boolean;
  role?: string;
  sessionId?: string;
  taskId?: string;
  instructions?: string;
  /** Omit the artifact/tool rows (a failed turn produces neither). */
  bare?: boolean;
  /** Pin the task timestamp (defaults to "now" so the client deadline does not fire). */
  createdAt?: string;
}

function sessionDetail(overrides: SessionOverrides = {}) {
  const taskStatus = overrides.taskStatus ?? 'completed';
  const role = overrides.role ?? 'WATCHTOWER';
  const sessionId = overrides.sessionId ?? 'agent-session:ags_chat_001';
  const taskId = overrides.taskId ?? 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV';
  const instructions = overrides.instructions ?? 'Sweep the current alerts';
  // Task timestamps are "just now": the panel's client deadline is anchored on the task
  // row, so a hard-coded past timestamp would (correctly) resolve a running task as timed
  // out the moment it renders.
  const taskCreatedAt = overrides.createdAt ?? new Date().toISOString();
  return {
    schemaVersion: 1,
    session: {
      schemaVersion: 1,
      id: sessionId,
      runId: RUN_ID,
      incidentId: null,
      role,
      state: 'verifying',
      traceId: TRACE,
      createdAt: '2026-07-22T00:00:00.000Z',
      updatedAt: '2026-07-22T00:00:00.000Z',
    },
    tasks: [
      {
        schemaVersion: 1,
        id: taskId,
        sessionId,
        runId: RUN_ID,
        incidentId: null,
        status: taskStatus,
        attempt: 1,
        idempotencyKey: 'chat-1',
        traceId: TRACE,
        providerId: 'openai-compatible',
        instructions,
        errorCode: overrides.withError ? 'PROVIDER_FAILURE' : null,
        errorMessage: overrides.withError ? 'Model timed out' : null,
        createdAt: taskCreatedAt,
        updatedAt: taskCreatedAt,
      },
    ],
    transitions: [],
    toolInvocations: overrides.bare
      ? []
      : [
          {
            schemaVersion: 1,
            id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FAV',
            taskId,
            sessionId,
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
    artifacts: overrides.bare
      ? []
      : [
          {
            schemaVersion: 1,
            id: 'aaf_01ARZ3NDEKTSV4RRFFQ69G5FAV',
            taskId,
            sessionId,
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

function watchtowerSessionDetail(overrides: SessionOverrides = {}) {
  return sessionDetail(overrides);
}

/** The TRACE thread used by the role-isolation tests. */
function traceSessionDetail(overrides: SessionOverrides = {}) {
  return sessionDetail({
    role: 'TRACE',
    sessionId: 'agent-session:ags_chat_trace',
    taskId: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FBV',
    instructions: 'Trace the unseen-source alerts',
    bare: true,
    ...overrides,
  });
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
    // Scoped to the turn card: the sr-only status region legitimately echoes the same
    // words for screen readers, so an unscoped text query matches twice.
    const turnError = await within(panel).findByTestId('agent-chat-turn-error');
    expect(turnError).toHaveTextContent('Model timed out');
    expect(turnError).toHaveTextContent('PROVIDER_FAILURE');
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
        // The third load (triggered by the POST's own success invalidation) returns the
        // finished turn, which is what re-enables the composer: the role stays busy until
        // its *task* is terminal, not merely until the HTTP request returns.
        const sessions =
          getCalls === 1
            ? []
            : [
                watchtowerSessionDetail({
                  taskStatus: getCalls >= 3 ? 'completed' : 'running',
                  instructions: 'Sweep the run now',
                }),
              ];
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

/**
 * BUG-023: switching roles used to relabel the single in-flight task ("TRACE is
 * investigating…" became "ORACLE is investigating…"), keep the composer disabled for every
 * role, and show no task identity.
 *
 * BUG-024: a failed/cancelled task did not reliably resolve the card — it could stay
 * "investigating…"/"Sending…" with the input disabled, no retry, no error surface.
 */
describe('AgentChatPanel task lifecycle', () => {
  beforeEach(() => {
    apiFetch.mockReset();
    runIncidents.mockReturnValue({ isSuccess: true, data: [{ id: 'incident:inc_001' }] });
  });
  afterEach(() => {
    cleanup();
  });

  async function selectRole(name: string) {
    await userEvent.click(screen.getByTestId(`agent-chat-role-${name}`));
  }

  it('keeps task identity per role when the operator switches mid-flight', async () => {
    // TRACE's POST never resolves: the operator switches away while it is genuinely running.
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ sessions: [] }));
      }
      return new Promise<Response>(() => {
        /* never settles */
      });
    });

    renderPanel();
    await screen.findByTestId('agent-chat-panel');

    await selectRole('TRACE');
    await userEvent.type(
      screen.getByLabelText<HTMLTextAreaElement>(/Message to TRACE/),
      'Trace the unseen-source alerts',
    );
    await userEvent.click(screen.getByRole('button', { name: /Send to TRACE/ }));

    const panel = screen.getByTestId('agent-chat-panel');
    expect(await within(panel).findByTestId('agent-chat-working')).toHaveTextContent(
      'TRACE is investigating…',
    );
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to TRACE/)).toBeDisabled();
    expect(screen.getByTestId('agent-chat-role-TRACE')).toHaveAttribute('data-busy', 'true');

    // Switch to ORACLE: the view changes, the task does not move with it.
    await selectRole('ORACLE');

    expect(within(panel).queryByTestId('agent-chat-working')).not.toBeInTheDocument();
    expect(within(panel).queryByText(/ORACLE is investigating/)).not.toBeInTheDocument();
    expect(within(panel).queryByText('Trace the unseen-source alerts')).not.toBeInTheDocument();
    // ORACLE has no task of its own, so its composer is usable.
    const oracleComposer = screen.getByLabelText<HTMLTextAreaElement>(/Message to ORACLE/);
    expect(oracleComposer).toBeEnabled();
    expect(screen.getByTestId('agent-chat-role-ORACLE')).toHaveAttribute('data-busy', 'false');
    // …and TRACE is still visibly the owner of the in-flight work.
    expect(screen.getByTestId('agent-chat-role-TRACE')).toHaveAttribute('data-busy', 'true');
    expect(screen.getByTestId('agent-chat-others')).toHaveTextContent(
      'Still working elsewhere: TRACE',
    );

    // BASTION likewise: a third role change must not adopt TRACE's turn.
    await selectRole('BASTION');
    expect(within(panel).queryByText(/BASTION is investigating/)).not.toBeInTheDocument();
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to BASTION/)).toBeEnabled();

    // Coming back to TRACE restores its own prompt and busy state.
    await selectRole('TRACE');
    expect(within(panel).getByTestId('agent-chat-working')).toHaveTextContent(
      'TRACE is investigating…',
    );
    expect(within(panel).getByText('Trace the unseen-source alerts')).toBeInTheDocument();
  });

  it('resolves a role whose task fails while a different role is selected', async () => {
    let failed = false;
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(
          jsonResponse({
            sessions: [
              traceSessionDetail(
                failed ? { taskStatus: 'failed', withError: true } : { taskStatus: 'running' },
              ),
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });

    const { client } = renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await waitFor(() => {
      expect(screen.getByTestId('agent-chat-role-TRACE')).toHaveAttribute('data-busy', 'true');
    });

    // Operator is looking at WATCHTOWER (the default) when TRACE's task fails.
    failed = true;
    await client.invalidateQueries({ queryKey: queryKeys.agentSessions.listForRun(RUN_ID) });

    // The terminal transition resolves TRACE even though TRACE is not selected.
    await waitFor(() => {
      expect(screen.getByTestId('agent-chat-role-TRACE')).toHaveAttribute('data-busy', 'false');
    });
    expect(screen.queryByTestId('agent-chat-others')).not.toBeInTheDocument();

    await selectRole('TRACE');
    const panel = screen.getByTestId('agent-chat-panel');
    expect(within(panel).getByTestId('agent-chat-turn-error')).toHaveTextContent('Model timed out');
    expect(within(panel).getByText(/PROVIDER_FAILURE/)).toBeInTheDocument();
    // Task identity is visible for support, and the composer is usable again.
    expect(within(panel).getByTestId('agent-chat-turn-diagnostics')).toHaveTextContent(
      'atk_01ARZ3NDEKTSV4RRFFQ69G5FBV',
    );
    expect(within(panel).getByTestId('agent-chat-turn-diagnostics')).toHaveTextContent(TRACE);
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to TRACE/)).toBeEnabled();
  });

  it('applies a repeated terminal transition idempotently', async () => {
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(
          jsonResponse({
            sessions: [traceSessionDetail({ taskStatus: 'failed', withError: true })],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });

    const { client } = renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await selectRole('TRACE');
    const panel = screen.getByTestId('agent-chat-panel');
    await within(panel).findByTestId('agent-chat-turn-error');

    // The same terminal row arrives again (a duplicate agent.task.failed, or the poll
    // refetch returning what it already had). Re-applying it must change nothing.
    await client.invalidateQueries({ queryKey: queryKeys.agentSessions.listForRun(RUN_ID) });
    await client.invalidateQueries({ queryKey: queryKeys.agentSessions.listForRun(RUN_ID) });

    await waitFor(() => {
      expect(within(panel).getAllByTestId('agent-chat-turn-error')).toHaveLength(1);
    });
    expect(within(panel).getAllByTestId('agent-chat-retry')).toHaveLength(1);
    expect(within(panel).queryByTestId('agent-chat-working')).not.toBeInTheDocument();
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to TRACE/)).toBeEnabled();
    expect(screen.getByTestId('agent-chat-role-TRACE')).toHaveAttribute('data-busy', 'false');
  });

  it('retries a failed turn as a new task on the same role', async () => {
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(
          jsonResponse({
            sessions: [traceSessionDetail({ taskStatus: 'failed', withError: true })],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ status: 'completed' }));
    });

    renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await selectRole('TRACE');
    const panel = screen.getByTestId('agent-chat-panel');
    await within(panel).findByTestId('agent-chat-turn-error');

    await userEvent.click(within(panel).getByTestId('agent-chat-retry'));

    await waitFor(() => {
      const postCall = apiFetch.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      );
      expect(postCall).toBeTruthy();
      // A NEW task on TRACE's own session — not a re-run of the old task, and not a
      // session belonging to another role.
      expect(postCall?.[0]).toBe('/api/v1/agent-sessions/agent-session:ags_chat_trace/tasks');
      const body = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
        instructions?: string;
      };
      expect(body.instructions).toBe('Trace the unseen-source alerts');
    });
  });

  it('surfaces a transport failure that never created a task, with retry', async () => {
    apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ sessions: [] }));
      }
      return Promise.resolve(
        jsonResponse(
          { code: 'PROVIDER_FAILURE', message: 'Provider request was cancelled' },
          false,
          502,
        ),
      );
    });

    renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await userEvent.type(
      screen.getByLabelText<HTMLTextAreaElement>(/Message to WATCHTOWER/),
      'Sweep the run now',
    );
    await userEvent.click(screen.getByRole('button', { name: /Send to WATCHTOWER/ }));

    const panel = screen.getByTestId('agent-chat-panel');
    const banner = await within(panel).findByTestId('agent-chat-role-error');
    expect(banner).toHaveTextContent('Provider request was cancelled');
    expect(banner).toHaveTextContent('PROVIDER_FAILURE');
    expect(within(banner).getByTestId('agent-chat-retry')).toBeInTheDocument();
    // The role must not be left busy after its request resolved.
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to WATCHTOWER/)).toBeEnabled();
    expect(screen.getByTestId('agent-chat-role-WATCHTOWER')).toHaveAttribute('data-busy', 'false');
  });
});

describe('AgentChatPanel BASTION incident prerequisite', () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockResolvedValue(jsonResponse({ sessions: [] }));
  });
  afterEach(() => {
    cleanup();
    runIncidents.mockReturnValue({ isSuccess: true, data: [{ id: 'incident:inc_001' }] });
  });

  async function selectBastion() {
    renderPanel();
    await screen.findByTestId('agent-chat-panel');
    await userEvent.click(screen.getByRole('radio', { name: 'BASTION' }));
  }

  it('blocks BASTION with a named prerequisite when the run has no incident', async () => {
    runIncidents.mockReturnValue({ isSuccess: true, data: [] });

    await selectBastion();

    const notice = screen.getByTestId('agent-chat-incident-required');
    expect(notice).toHaveTextContent('Incident required');
    // The way out must be one that actually works. Asking WATCHTOWER here cannot open a
    // case — copilot turns are run-scoped and the executor skips role post-processing for
    // them — so the notice must not send the operator down that path.
    expect(notice).toHaveTextContent(/[Pp]in a hypothesis/);
    expect(notice).not.toHaveTextContent(/WATCHTOWER/);
    expect(within(notice).getByRole('link', { name: /incident queue/i })).toHaveAttribute(
      'href',
      '/incidents',
    );
  });

  it('does not send a doomed BASTION request while the prerequisite is unmet', async () => {
    runIncidents.mockReturnValue({ isSuccess: true, data: [] });

    await selectBastion();

    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to BASTION/)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Send to BASTION/ })).toBeDisabled();
    // Only the session read fired; no POST was attempted.
    const writes = apiFetch.mock.calls.filter((call) => {
      const init = call[1] as RequestInit | undefined;
      return (init?.method ?? 'GET') !== 'GET';
    });
    expect(writes).toHaveLength(0);
  });

  it('leaves BASTION available once the run has an open incident', async () => {
    runIncidents.mockReturnValue({ isSuccess: true, data: [{ id: 'incident:inc_001' }] });

    await selectBastion();

    expect(screen.queryByTestId('agent-chat-incident-required')).not.toBeInTheDocument();
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to BASTION/)).toBeEnabled();
  });

  it('does not invent a block when the incident list cannot be read', async () => {
    // A failed read is "unknown", not "none" — blocking here would strand BASTION on a
    // transient API error. The empty list proves it is `isSuccess` doing the gating.
    runIncidents.mockReturnValue({ isSuccess: false, data: [] });

    await selectBastion();

    expect(screen.queryByTestId('agent-chat-incident-required')).not.toBeInTheDocument();
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Message to BASTION/)).toBeEnabled();
  });
});
