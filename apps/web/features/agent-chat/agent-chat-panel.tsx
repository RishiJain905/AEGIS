'use client';

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';

import {
  NodeStatus,
  type AgentArtifactV1,
  type AgentSessionDetailV1,
  type AgentTaskV1,
  type ToolInvocationV1,
} from '@aegis/contracts-ts';
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  useReducedMotion,
} from '@aegis/ui';

import Link from 'next/link';

import { useRunIncidents } from '@/features/incidents';
import { ApiClientError } from '@/lib/api/types';

import {
  CLIENT_DEADLINE_ERROR_CODE,
  COPILOT_TASK_DEADLINE_MS,
  DEADLINE_POLL_MS,
  copilotTaskReducer,
  deriveRoleTurn,
  initialCopilotTaskMap,
  isTerminalTaskStatus,
  latestSessionForRole,
  latestTaskOf,
  otherBusyRoles,
  type CopilotClientError,
  type RoleTurnView,
} from './copilot-task-state';
import {
  CHAT_ROLES,
  useRunAgentSessions,
  useSendAgentMessage,
  type ChatRole,
} from './use-agent-chat';

const ROLE_BLURB: Record<ChatRole, string> = {
  WATCHTOWER: 'Sweep current alerts and telemetry, and recommend what to triage first.',
  TRACE: 'Investigate a specific asset, hypothesis, or lead across the run.',
  ORACLE: 'Weigh competing explanations for what you are seeing.',
  BASTION: 'Draft proportionate containment (needs an open incident to propose actions).',
};

const ROLE_PLACEHOLDER: Record<ChatRole, string> = {
  WATCHTOWER: 'Ask WATCHTOWER to sweep the current alerts and telemetry…',
  TRACE: 'Point TRACE at an asset or hypothesis to investigate…',
  ORACLE: 'Ask ORACLE to weigh competing explanations…',
  BASTION: 'Ask BASTION to draft containment options…',
};

const MAX_INSTRUCTIONS = 4000;

const INCIDENT_REQUIRED_PLACEHOLDER = 'BASTION needs an open incident before it can propose…';

/**
 * BASTION's prerequisite, stated where the operator hits it.
 *
 * The named way forward is deliberately *not* "ask WATCHTOWER". Copilot messages open a
 * run-scoped session (`incidentId: null`), and the executor skips role post-processing for
 * run-scoped tasks, so a WATCHTOWER turn here can never open a case however well it runs.
 * Autonomy triage does not open one either. The only thing that opens a case on a live run
 * today is an operator act anchoring the operator incident — pinning a hypothesis being the
 * cheapest and most reversible — so that is what this points at.
 */
function IncidentRequiredNotice() {
  return (
    <Alert variant="warning" data-testid="agent-chat-incident-required">
      <span className="flex flex-col gap-1">
        <span className="font-medium">Incident required</span>
        <span>
          BASTION proposes containment against an open case, and this run has none yet. Pin a
          hypothesis in the operator console — that opens the case BASTION needs. Alerts on their
          own do not open one.
        </span>
        <Link
          href="/incidents"
          className="w-fit underline underline-offset-2 hover:text-[var(--aegis-accent-strong)]"
        >
          Review the incident queue
        </Link>
      </span>
    </Alert>
  );
}

interface ChatTurn {
  taskId: string;
  instructions: string | null;
  task: AgentTaskV1;
  artifact: AgentArtifactV1 | undefined;
  tools: ToolInvocationV1[];
}

/** Build the ordered turns for a role's session (operator instruction -> result). */
function buildTurns(detail: AgentSessionDetailV1): ChatTurn[] {
  const stepByTask = new Map<string, AgentArtifactV1>();
  for (const artifact of detail.artifacts) {
    if (artifact.artifactType === 'step_result') {
      stepByTask.set(artifact.taskId, artifact);
    }
  }
  const toolsByTask = new Map<string, ToolInvocationV1[]>();
  for (const inv of detail.toolInvocations) {
    const list = toolsByTask.get(inv.taskId) ?? [];
    list.push(inv);
    toolsByTask.set(inv.taskId, list);
  }
  return detail.tasks.map((task) => ({
    taskId: task.id,
    instructions: task.instructions ?? null,
    task,
    artifact: stepByTask.get(task.id),
    tools: toolsByTask.get(task.id) ?? [],
  }));
}

function toolBadgeStatus(status: ToolInvocationV1['status']) {
  switch (status) {
    case 'success':
      return NodeStatus.NORMAL;
    case 'rejected':
      return NodeStatus.SUSPICIOUS;
    case 'failed':
      return NodeStatus.COMPROMISED;
    default:
      return NodeStatus.SUSPICIOUS;
  }
}

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
        Confidence
      </span>
      <div
        className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--aegis-border-subtle)]"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Agent confidence"
      >
        <div className="h-full bg-[var(--aegis-accent)]" style={{ width: `${String(pct)}%` }} />
      </div>
      <span className="font-mono text-[10px] text-[var(--aegis-text-secondary)]">{pct}%</span>
    </div>
  );
}

function ArtifactBody({ artifact }: { artifact: AgentArtifactV1 }) {
  const payload = artifact.payload as {
    rationale?: unknown;
    confidence?: unknown;
    evidenceCitations?: unknown;
  };
  const rationale = typeof payload.rationale === 'string' ? payload.rationale : '';
  const confidence = typeof payload.confidence === 'number' ? payload.confidence : null;
  const citations = Array.isArray(payload.evidenceCitations)
    ? (payload.evidenceCitations as { evidenceId?: unknown }[])
    : [];
  return (
    <div className="flex flex-col gap-2">
      {rationale ? (
        <p className="whitespace-pre-wrap text-sm text-[var(--aegis-text-primary)]">{rationale}</p>
      ) : (
        <p className="text-sm italic text-[var(--aegis-text-muted)]">No rationale returned.</p>
      )}
      {confidence !== null ? <ConfidenceMeter value={confidence} /> : null}
      {citations.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)]">
            Evidence
          </span>
          {citations.map((citation, index) => {
            const id = typeof citation.evidenceId === 'string' ? citation.evidenceId : '';
            return id ? (
              <code
                key={`${id}-${String(index)}`}
                className="rounded-[var(--aegis-radius-sm)] bg-[var(--aegis-surface-raised)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--aegis-text-secondary)]"
              >
                {id}
              </code>
            ) : null;
          })}
        </div>
      ) : null}
    </div>
  );
}

function ToolChips({ tools }: { tools: ToolInvocationV1[] }) {
  if (tools.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Tool activity">
      {tools.map((tool) => (
        <Badge key={tool.id} nodeStatus={toolBadgeStatus(tool.status)}>
          <span className="font-mono text-[10px]">{tool.toolName}</span>
          <span className="ml-1 text-[9px] text-[var(--aegis-text-muted)]">
            {tool.durationMs}ms
          </span>
        </Badge>
      ))}
    </div>
  );
}

const FAILURE_FALLBACK_MESSAGE: Record<string, string> = {
  failed: 'The agent task failed.',
  cancelled: 'The agent task was cancelled.',
  timed_out: 'The agent task timed out.',
};

/**
 * Identity line for a turn: the task id and the trace/request id.
 *
 * The error *code* is deliberately not repeated here — the failure alert above already
 * carries it, and duplicating it makes the card noisier without adding information.
 */
function TurnDiagnostics({ taskId, traceId }: { taskId: string | null; traceId: string | null }) {
  const parts: { label: string; value: string }[] = [];
  if (taskId) {
    parts.push({ label: 'task', value: taskId });
  }
  if (traceId) {
    parts.push({ label: 'trace', value: traceId });
  }
  if (parts.length === 0) {
    return null;
  }
  return (
    <p
      className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] text-[var(--aegis-text-muted)]"
      data-testid="agent-chat-turn-diagnostics"
    >
      {parts.map((part) => (
        <span key={part.label}>
          <span className="uppercase tracking-wide">{part.label} </span>
          <span className="text-[var(--aegis-text-secondary)]">{part.value}</span>
        </span>
      ))}
    </p>
  );
}

function TurnView({
  turn,
  clientTimedOut = false,
  onRetry,
}: {
  turn: ChatTurn;
  /**
   * The client safety deadline fired against this turn while the backend still
   * reports it as in flight — render it as resolved rather than eternally "Working…".
   */
  clientTimedOut?: boolean;
  onRetry?: (instructions: string) => void;
}) {
  const backendStatus = turn.task.status;
  const status =
    clientTimedOut && !isTerminalTaskStatus(backendStatus) ? 'timed_out' : backendStatus;
  const isFailed = status === 'failed' || status === 'timed_out' || status === 'cancelled';
  const isWorking = status === 'queued' || status === 'running';
  const errorCode =
    clientTimedOut && !isTerminalTaskStatus(backendStatus)
      ? CLIENT_DEADLINE_ERROR_CODE
      : (turn.task.errorCode ?? null);
  const errorMessage =
    clientTimedOut && !isTerminalTaskStatus(backendStatus)
      ? `No result after ${String(Math.round(COPILOT_TASK_DEADLINE_MS / 60_000))} minutes. The task never reported a terminal state.`
      : (turn.task.errorMessage ?? FAILURE_FALLBACK_MESSAGE[status] ?? 'The agent task failed.');
  const retryInstructions = turn.instructions;
  return (
    <li className="flex flex-col gap-2">
      {turn.instructions ? (
        <div className="self-end rounded-[var(--aegis-radius-md)] bg-[var(--aegis-accent-soft)] px-3 py-2">
          <p className="whitespace-pre-wrap text-sm text-[var(--aegis-text-primary)]">
            {turn.instructions}
          </p>
        </div>
      ) : null}
      <div className="flex flex-col gap-2 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2">
        <ToolChips tools={turn.tools} />
        {isWorking ? (
          <>
            <p className="text-sm text-[var(--aegis-text-muted)]">Working…</p>
            <TurnDiagnostics taskId={turn.taskId} traceId={turn.task.traceId} />
          </>
        ) : isFailed ? (
          <div className="flex flex-col gap-2" data-testid="agent-chat-turn-error">
            <Alert variant="error">
              {errorMessage}
              {errorCode ? <span className="ml-1 font-mono text-[10px]">({errorCode})</span> : null}
            </Alert>
            <TurnDiagnostics taskId={turn.taskId} traceId={turn.task.traceId} />
            {onRetry && retryInstructions ? (
              <div>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  data-testid="agent-chat-retry"
                  onClick={() => {
                    onRetry(retryInstructions);
                  }}
                >
                  Retry
                </Button>
              </div>
            ) : null}
          </div>
        ) : turn.artifact ? (
          <ArtifactBody artifact={turn.artifact} />
        ) : (
          <p className="text-sm italic text-[var(--aegis-text-muted)]">
            No result artifact was produced.
          </p>
        )}
      </div>
    </li>
  );
}

export interface AgentChatPanelProps {
  runId: string;
  /**
   * A keystroke routed here from outside (the cockpit console's command-line behaviour):
   * each new `token` appends `text` to the draft and focuses the composer. Monotonic
   * tokens make application exactly-once.
   */
  composerSeed?: { text: string; token: number } | null;
}

/** Turn an unknown mutation rejection into something an operator can act on. */
function toClientError(error: unknown): CopilotClientError {
  if (error instanceof ApiClientError) {
    return { code: error.code, message: error.message, traceId: error.traceId ?? null };
  }
  if (error instanceof Error) {
    // `AbortSignal.timeout` rejects with a TimeoutError whose message ("signal timed out")
    // means nothing to an operator and — critically — does not mean the *task* died: the
    // backend usually keeps working. Say so, and let the authoritative task row decide
    // whether the turn is actually over.
    const aborted = error.name === 'TimeoutError' || error.name === 'AbortError';
    return {
      code: aborted ? 'REQUEST_TIMEOUT' : null,
      message: aborted
        ? 'The request to the agent service timed out. If the task is still running it will resolve here on its own.'
        : error.message,
      traceId: null,
    };
  }
  return { code: null, message: 'The request failed.', traceId: null };
}

export function AgentChatPanel({ runId, composerSeed }: AgentChatPanelProps) {
  // Operator threads only — the autonomy worker's background triage sessions are not
  // this conversation and must not appear in it.
  const sessionsQuery = useRunAgentSessions(runId, 'operator');
  const sendMessage = useSendAgentMessage(runId);
  const reducedMotion = useReducedMotion();
  const incidentsQuery = useRunIncidents(runId);

  const [role, setRole] = useState<ChatRole>('WATCHTOWER');
  const [draft, setDraft] = useState('');
  // Per-role client state. Everything the operator sees — busy, failed, succeeded — is
  // *derived* from the authoritative task rows rather than stored, so a role's turn can
  // never be re-owned by whichever role happens to be selected (BUG-023) and a repeated
  // terminal transition is a no-op by construction (BUG-024).
  const [localTasks, dispatch] = useReducer(copilotTaskReducer, initialCopilotTaskMap);
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const turnListRef = useRef<HTMLDivElement>(null);

  // Apply a routed keystroke exactly once per token: append it and hand the composer focus,
  // so typing on the console flows straight into the conversation.
  const lastSeedTokenRef = useRef(0);
  useEffect(() => {
    if (!composerSeed || composerSeed.token === lastSeedTokenRef.current) {
      return;
    }
    lastSeedTokenRef.current = composerSeed.token;
    setDraft((current) => current + composerSeed.text);
    draftRef.current?.focus();
  }, [composerSeed]);

  // One entry per role: its newest operator session plus the derived state of the turn
  // that role owns. Computed for *every* role, not just the selected one, so a task that
  // reaches a terminal state while the operator is looking elsewhere still resolves its
  // own card and re-enables its own composer.
  const roleViews = useMemo(() => {
    const details = sessionsQuery.data;
    const entries = CHAT_ROLES.map((candidate) => {
      const session = latestSessionForRole(details, candidate);
      return [
        candidate,
        { session, view: deriveRoleTurn(candidate, latestTaskOf(session), localTasks[candidate]) },
      ] as const;
    });
    return Object.fromEntries(entries) as Record<
      ChatRole,
      { session: AgentSessionDetailV1 | undefined; view: RoleTurnView }
    >;
  }, [sessionsQuery.data, localTasks]);

  const views = useMemo(() => {
    const entries = CHAT_ROLES.map((candidate) => [candidate, roleViews[candidate].view] as const);
    return Object.fromEntries(entries) as Record<ChatRole, RoleTurnView>;
  }, [roleViews]);

  const roleSession = roleViews[role].session;
  const view = roleViews[role].view;
  /** Busy state of the SELECTED role only — never a global "something is in flight". */
  const pending = view.busy;
  const retrying = sendMessage.retryingRoles.includes(role);

  const turns = useMemo(() => (roleSession ? buildTurns(roleSession) : []), [roleSession]);

  // Client-side safety deadline. Without it a task whose terminal transition never lands
  // (a provider that hangs, a dropped socket, a worker that died mid-turn) leaves the card
  // spinning forever with the composer disabled. Resolving into an explicit timed-out state
  // that offers Retry always beats an unbounded spinner.
  useEffect(() => {
    const watched = CHAT_ROLES.map((candidate) => views[candidate]).filter(
      (candidate) => candidate.busy && candidate.startedAtMs !== null && candidate.turnKey !== null,
    );
    if (watched.length === 0) {
      return undefined;
    }
    const tick = () => {
      const now = Date.now();
      for (const candidate of watched) {
        if (
          candidate.startedAtMs !== null &&
          candidate.turnKey !== null &&
          now - candidate.startedAtMs >= COPILOT_TASK_DEADLINE_MS
        ) {
          // Idempotent: the reducer returns the same state object once a turn is already
          // deadlined, so this cannot drive a render loop.
          dispatch({ type: 'deadline-reached', role: candidate.role, turnKey: candidate.turnKey });
        }
      }
    };
    tick();
    const timer = setInterval(tick, DEADLINE_POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [views]);

  // BASTION's containment tooling is incident-scoped: with no case open on the run, its
  // proposal tool is rejected and the turn burns a provider call to say nothing useful.
  // Block the send instead, and name the way out. An unreadable incident list is not
  // treated as "no incidents" — a failed read must not invent a block that isn't there.
  const incidentRequired =
    role === 'BASTION' && incidentsQuery.isSuccess && incidentsQuery.data.length === 0;

  // The realtime `agent.*` event invalidation (live-run-provider.tsx) refetches sessions
  // as soon as the backend creates the task — well before this request's own (inline,
  // potentially slow) response arrives. Once the real turn is visible the derived phase is
  // already `working`, which suppresses the optimistic placeholder below, so the submission
  // renders once, not twice.
  const showOptimisticTurn = view.phase === 'sending';
  const lastTurn = turns.length > 0 ? turns[turns.length - 1] : undefined;

  // Keep the newest turn in view: on mount (the sheet just opened) and whenever a turn
  // lands, the log scrolls to its end. Instant, so reduced motion has nothing to suppress.
  useEffect(() => {
    const list = turnListRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, [turns.length, showOptimisticTurn, role]);

  const send = useCallback(
    (instructions: string, target: ChatRole) => {
      const trimmed = instructions.trim();
      if (!trimmed || views[target].busy) {
        return;
      }
      dispatch({ type: 'submitted', role: target, instructions: trimmed, atMs: Date.now() });
      sendMessage.mutate(
        { role: target, instructions: trimmed, sessionId: roleViews[target].session?.session.id },
        {
          onSuccess: () => {
            draftRef.current?.focus();
          },
          onError: (error: unknown) => {
            dispatch({ type: 'send-failed', role: target, error: toClientError(error) });
          },
          onSettled: () => {
            dispatch({ type: 'send-settled', role: target });
          },
        },
      );
    },
    [roleViews, sendMessage, views],
  );

  const submit = () => {
    const instructions = draft.trim();
    if (!instructions || pending || incidentRequired) {
      return;
    }
    // Clear the composer the moment the operator sends, not when the (possibly
    // slow, inline-LLM) response comes back — the request is committed either way,
    // and a failure surfaces through the turn's error card, not by handing the text back.
    setDraft('');
    send(instructions, role);
  };

  /** Retry re-sends the same prompt as a brand new task on this role's own thread. */
  const retry = useCallback(
    (instructions: string) => {
      send(instructions, role);
    },
    [role, send],
  );

  const otherWorking = otherBusyRoles(views, role);
  const clientDeadlineHit =
    view.phase === 'timed_out' && view.errorCode === CLIENT_DEADLINE_ERROR_CODE;
  const resolvedWithError =
    view.phase === 'failed' || view.phase === 'timed_out' || view.phase === 'cancelled';
  // A transport failure that never produced a task row has no turn to render it, so the
  // role-level notice below is the only place it can surface.
  const orphanClientError = view.phase === 'failed' && view.taskId === null;

  const liveStatus = retrying
    ? `${role} task failed — retrying once…`
    : pending
      ? `${role} is investigating…`
      : resolvedWithError
        ? `The last ${role} task ended in ${view.phase}. ${view.errorMessage ?? ''}`.trim()
        : '';

  return (
    <Panel
      title="AI Copilot"
      description="Task and converse with the defensive agents on this run."
      density="compact"
      data-tutorial-id="agent-chat"
      data-testid="agent-chat-panel"
      className="min-h-0 flex-1"
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Agent role">
          {CHAT_ROLES.map((candidate) => {
            const selected = candidate === role;
            const candidateBusy = views[candidate].busy;
            return (
              <button
                key={candidate}
                type="button"
                role="radio"
                aria-checked={selected}
                data-testid={`agent-chat-role-${candidate}`}
                data-busy={candidateBusy ? 'true' : 'false'}
                onClick={() => {
                  // Selecting a role changes the VIEW only. Every role keeps its own
                  // in-flight task, busy state and history; nothing is renamed or cancelled.
                  setRole(candidate);
                }}
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  selected
                    ? 'border-[var(--aegis-accent)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-text-primary)]'
                    : 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-secondary)] hover:border-[var(--aegis-border-strong)]'
                }`}
              >
                {candidate}
                {candidateBusy ? (
                  <>
                    <span
                      aria-hidden="true"
                      className={`h-1.5 w-1.5 rounded-full bg-[var(--aegis-accent)] ${
                        reducedMotion ? '' : 'animate-pulse'
                      }`}
                    />
                    <span className="sr-only">{`${candidate} task in flight`}</span>
                  </>
                ) : null}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--aegis-text-muted)]">{ROLE_BLURB[role]}</p>
        {otherWorking.length > 0 ? (
          <p className="text-[10px] text-[var(--aegis-text-muted)]" data-testid="agent-chat-others">
            {`Still working elsewhere: ${otherWorking.join(', ')}`}
          </p>
        ) : null}

        <div
          ref={turnListRef}
          className="flex min-h-[8rem] flex-1 flex-col gap-3 overflow-y-auto pr-1"
          aria-live="polite"
          aria-busy={pending}
        >
          {sessionsQuery.isPending ? (
            <LoadingState message="Loading copilot history…" />
          ) : sessionsQuery.isError ? (
            <ErrorState
              title="Could not load the copilot"
              message="Retry to reconnect to the agents."
              onRetry={() => void sessionsQuery.refetch()}
            />
          ) : turns.length === 0 && !pending ? (
            <EmptyState title={`No ${role} activity yet`} description={ROLE_BLURB[role]} />
          ) : (
            <ul className="flex flex-col gap-4">
              {turns.map((turn) => (
                <TurnView
                  key={turn.taskId}
                  turn={turn}
                  // The client deadline only ever applies to the turn it fired against.
                  clientTimedOut={clientDeadlineHit && turn.taskId === view.turnKey}
                  // Retry lives on the newest turn only, and only once the role is free.
                  onRetry={turn.taskId === lastTurn?.taskId && !pending ? retry : undefined}
                />
              ))}
              {showOptimisticTurn ? (
                <li className="flex flex-col gap-2">
                  {localTasks[role].instructions ? (
                    <div className="self-end rounded-[var(--aegis-radius-md)] bg-[var(--aegis-accent-soft)] px-3 py-2">
                      <p className="whitespace-pre-wrap text-sm text-[var(--aegis-text-primary)]">
                        {localTasks[role].instructions}
                      </p>
                    </div>
                  ) : null}
                  <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2">
                    <p
                      className={`text-sm ${
                        retrying
                          ? 'text-[var(--aegis-risk-medium)]'
                          : 'text-[var(--aegis-text-muted)]'
                      } ${reducedMotion ? '' : 'animate-pulse'}`}
                      data-testid={retrying ? 'agent-chat-retrying' : 'agent-chat-working'}
                    >
                      {retrying
                        ? `${role} task failed — retrying once…`
                        : `${role} is investigating…`}
                    </p>
                  </div>
                </li>
              ) : null}
            </ul>
          )}
        </div>

        <span className="sr-only" role="status" aria-live="polite">
          {liveStatus}
        </span>

        {incidentRequired ? <IncidentRequiredNotice /> : null}

        {orphanClientError ? (
          <div className="flex flex-col gap-2" data-testid="agent-chat-role-error">
            <Alert variant="error">
              {view.errorMessage ?? 'The request failed.'}
              {view.errorCode ? (
                <span className="ml-1 font-mono text-[10px]">({view.errorCode})</span>
              ) : null}
            </Alert>
            <TurnDiagnostics taskId={view.taskId} traceId={view.traceId} />
            {view.retryInstructions ? (
              <div>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  data-testid="agent-chat-retry"
                  onClick={() => {
                    if (view.retryInstructions) {
                      retry(view.retryInstructions);
                    }
                  }}
                >
                  Retry
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}

        <form
          data-tutorial-id="agent-chat-composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
          className="flex flex-col gap-2"
        >
          <label htmlFor="agent-chat-input" className="sr-only">
            Message to {role}
          </label>
          <textarea
            id="agent-chat-input"
            ref={draftRef}
            value={draft}
            maxLength={MAX_INSTRUCTIONS}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            rows={2}
            placeholder={incidentRequired ? INCIDENT_REQUIRED_PLACEHOLDER : ROLE_PLACEHOLDER[role]}
            disabled={pending || incidentRequired}
            className="w-full resize-none rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-3 py-2 text-sm text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[var(--aegis-text-muted)]">
              Enter to send · Shift+Enter for a new line
            </span>
            <Button
              type="submit"
              disabled={pending || incidentRequired || draft.trim().length === 0}
            >
              {pending ? 'Sending…' : `Send to ${role}`}
            </Button>
          </div>
        </form>
      </div>
    </Panel>
  );
}
