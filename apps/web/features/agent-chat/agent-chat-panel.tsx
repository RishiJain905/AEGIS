'use client';

import { useMemo, useRef, useState } from 'react';

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
          <span className="ml-1 text-[9px] text-[var(--aegis-text-muted)]">{tool.durationMs}ms</span>
        </Badge>
      ))}
    </div>
  );
}

function TurnView({ turn }: { turn: ChatTurn }) {
  const status = turn.task.status;
  const isFailed = status === 'failed' || status === 'timed_out';
  const isWorking = status === 'queued' || status === 'running';
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
          <p className="text-sm text-[var(--aegis-text-muted)]">Working…</p>
        ) : isFailed ? (
          <Alert variant="error">
            {turn.task.errorMessage ?? 'The agent task failed.'}
            {turn.task.errorCode ? (
              <span className="ml-1 font-mono text-[10px]">({turn.task.errorCode})</span>
            ) : null}
          </Alert>
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
}

export function AgentChatPanel({ runId }: AgentChatPanelProps) {
  const sessionsQuery = useRunAgentSessions(runId);
  const sendMessage = useSendAgentMessage(runId);
  const reducedMotion = useReducedMotion();

  const [role, setRole] = useState<ChatRole>('WATCHTOWER');
  const [draft, setDraft] = useState('');
  const draftRef = useRef<HTMLTextAreaElement>(null);

  // Most recent session for the selected role (the active thread).
  const roleSession = useMemo<AgentSessionDetailV1 | undefined>(() => {
    const details = sessionsQuery.data ?? [];
    const forRole = details.filter((detail) => detail.session.role === role);
    return forRole.length > 0 ? forRole[forRole.length - 1] : undefined;
  }, [sessionsQuery.data, role]);

  const turns = useMemo(() => (roleSession ? buildTurns(roleSession) : []), [roleSession]);

  const pending = sendMessage.isPending;
  const retrying = sendMessage.isRetrying;

  const submit = () => {
    const instructions = draft.trim();
    if (!instructions || pending) {
      return;
    }
    sendMessage.mutate(
      { role, instructions, sessionId: roleSession?.session.id },
      {
        onSuccess: () => {
          setDraft('');
          draftRef.current?.focus();
        },
      },
    );
  };

  const liveStatus = retrying
    ? `${role} task failed — retrying once…`
    : pending
      ? `${role} is investigating…`
      : sendMessage.isError
        ? 'The last request failed.'
        : '';

  return (
    <Panel
      title="AI Copilot"
      description="Task and converse with the defensive agents on this run."
      density="compact"
      data-tutorial-id="agent-chat"
      data-testid="agent-chat-panel"
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Agent role">
          {CHAT_ROLES.map((candidate) => {
            const selected = candidate === role;
            return (
              <button
                key={candidate}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => {
                  setRole(candidate);
                }}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  selected
                    ? 'border-[var(--aegis-accent)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-text-primary)]'
                    : 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-secondary)] hover:border-[var(--aegis-border-strong)]'
                }`}
              >
                {candidate}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--aegis-text-muted)]">{ROLE_BLURB[role]}</p>

        <div
          className="flex max-h-[26rem] min-h-[8rem] flex-col gap-3 overflow-y-auto pr-1"
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
            <EmptyState
              title={`No ${role} activity yet`}
              description={ROLE_BLURB[role]}
            />
          ) : (
            <ul className="flex flex-col gap-4">
              {turns.map((turn) => (
                <TurnView key={turn.taskId} turn={turn} />
              ))}
              {pending ? (
                <li className="flex flex-col gap-2">
                  {draft.trim() ? (
                    <div className="self-end rounded-[var(--aegis-radius-md)] bg-[var(--aegis-accent-soft)] px-3 py-2">
                      <p className="whitespace-pre-wrap text-sm text-[var(--aegis-text-primary)]">
                        {draft.trim()}
                      </p>
                    </div>
                  ) : null}
                  <div className="rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-raised)] px-3 py-2">
                    <p
                      className={`text-sm ${
                        retrying ? 'text-[var(--aegis-risk-medium)]' : 'text-[var(--aegis-text-muted)]'
                      } ${reducedMotion ? '' : 'animate-pulse'}`}
                      data-testid={retrying ? 'agent-chat-retrying' : 'agent-chat-working'}
                    >
                      {retrying ? `${role} task failed — retrying once…` : `${role} is investigating…`}
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

        {sendMessage.isError ? (
          <Alert variant="error">
            {sendMessage.error instanceof Error
              ? sendMessage.error.message
              : 'The request failed.'}
          </Alert>
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
            placeholder={ROLE_PLACEHOLDER[role]}
            disabled={pending}
            className="w-full resize-none rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[var(--aegis-surface-base)] px-3 py-2 text-sm text-[var(--aegis-text-primary)] placeholder:text-[var(--aegis-text-muted)] focus:border-[var(--aegis-accent)] focus:outline-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[var(--aegis-text-muted)]">
              Enter to send · Shift+Enter for a new line
            </span>
            <Button type="submit" disabled={pending || draft.trim().length === 0}>
              {pending ? 'Sending…' : `Send to ${role}`}
            </Button>
          </div>
        </form>
      </div>
    </Panel>
  );
}
