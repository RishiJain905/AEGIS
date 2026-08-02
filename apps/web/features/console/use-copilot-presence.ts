'use client';

import { useEffect, useRef, useState } from 'react';

import type { AgentSessionDetailV1, AgentTaskV1 } from '@aegis/contracts-ts';

import {
  isInFlightTaskStatus,
  isTerminalTaskStatus,
  latestSessionForRole,
  latestTaskOf,
} from '@/features/agent-chat/copilot-task-state';
import { CHAT_ROLES, useRunAgentSessions, type ChatRole } from '@/features/agent-chat/use-agent-chat';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

/** How long the one-line reply preview stays beside the chip before folding into the badge. */
export const PREVIEW_VISIBLE_MS = 8_000;

export type CopilotPresencePhase = 'idle' | 'working' | 'unread' | 'failed';

export interface CopilotPresence {
  phase: CopilotPresencePhase;
  /** Roles whose turn is currently owned by the backend. */
  workingRoles: ChatRole[];
  /** Replies (or failures) that landed while the sheet was closed. Cleared on open. */
  unreadCount: number;
  /** First sentence of the newest unseen reply, or the first line of its error. */
  preview: string | null;
  previewRole: ChatRole | null;
  /** True when the unread set contains at least one failure. */
  hasFailure: boolean;
  /** Wall clock of the newest unread event — the chip keys its preview timer off this. */
  lastEventAt: number | null;
  /** Screen-reader announcement for the newest event ("WATCHTOWER replied"). */
  announcement: string | null;
}

interface UnreadState {
  count: number;
  preview: string | null;
  role: ChatRole | null;
  failed: boolean;
  at: number;
}

function firstSentence(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  const match = /^[\s\S]*?[.!?](?=\s|$)/.exec(trimmed);
  const sentence = (match ? match[0] : trimmed).trim();
  return sentence.length > 140 ? `${sentence.slice(0, 137)}…` : sentence;
}

function firstLine(text: string): string | null {
  const line = text.split('\n', 1)[0]?.trim() ?? '';
  return line.length === 0 ? null : line.length > 140 ? `${line.slice(0, 137)}…` : line;
}

function replyPreview(detail: AgentSessionDetailV1, task: AgentTaskV1): string | null {
  const artifact = detail.artifacts.find(
    (candidate) => candidate.artifactType === 'step_result' && candidate.taskId === task.id,
  );
  const payload = artifact?.payload as { rationale?: unknown } | undefined;
  return typeof payload?.rationale === 'string' ? firstSentence(payload.rationale) : null;
}

/**
 * The presence chip's state machine input: per-role working state plus the unread
 * contract. A chip must never swallow a result — a turn that reaches a terminal state
 * while the copilot sheet is closed becomes an unread event that persists until the
 * sheet opens, however long that takes and wherever the operator navigates within the
 * run. Opening the sheet clears it.
 *
 * Transitions are detected against the authoritative task rows (the same source the
 * chat panel derives from): a task previously seen in flight that is now terminal is an
 * event; tasks first seen already-terminal are history, not news.
 */
export function useCopilotPresence(runId: string): CopilotPresence {
  const sessionsQuery = useRunAgentSessions(runId, 'operator');
  const sheetOpen = useCockpitUiStore((state) => state.copilotSheetOpen);

  const statusesRef = useRef<Map<string, string>>(new Map());
  const [unread, setUnread] = useState<UnreadState | null>(null);

  // Detect in-flight → terminal transitions.
  useEffect(() => {
    const details = sessionsQuery.data;
    if (!details) {
      return;
    }
    const previous = statusesRef.current;
    const next = new Map<string, string>();
    const events: { role: ChatRole; detail: AgentSessionDetailV1; task: AgentTaskV1 }[] = [];
    for (const detail of details) {
      for (const task of detail.tasks) {
        next.set(task.id, task.status);
        const was = previous.get(task.id);
        if (
          was !== undefined &&
          !isTerminalTaskStatus(was) &&
          isTerminalTaskStatus(task.status)
        ) {
          events.push({ role: detail.session.role as ChatRole, detail, task });
        }
      }
    }
    statusesRef.current = next;
    const newest = events[events.length - 1];
    if (newest === undefined || sheetOpen) {
      return;
    }
    const failed = newest.task.status !== 'completed';
    const preview = failed
      ? (firstLine(newest.task.errorMessage ?? '') ?? 'The agent task failed.')
      : (replyPreview(newest.detail, newest.task) ?? 'Reply ready.');
    setUnread((current) => ({
      count: (current?.count ?? 0) + events.length,
      preview,
      role: newest.role,
      failed: (current?.failed ?? false) || failed,
      at: Date.now(),
    }));
  }, [sessionsQuery.data, sheetOpen]);

  // Opening the sheet is the read receipt.
  useEffect(() => {
    if (sheetOpen) {
      setUnread(null);
    }
  }, [sheetOpen]);

  const workingRoles = CHAT_ROLES.filter((role) => {
    const task = latestTaskOf(latestSessionForRole(sessionsQuery.data, role));
    return task !== undefined && isInFlightTaskStatus(task.status);
  });

  const phase: CopilotPresencePhase = unread
    ? unread.failed
      ? 'failed'
      : 'unread'
    : workingRoles.length > 0
      ? 'working'
      : 'idle';

  const announcement = unread?.role
    ? unread.failed
      ? `${unread.role} needs attention`
      : `${unread.role} replied`
    : null;

  return {
    phase,
    workingRoles,
    unreadCount: unread?.count ?? 0,
    preview: unread?.preview ?? null,
    previewRole: unread?.role ?? null,
    hasFailure: unread?.failed ?? false,
    lastEventAt: unread?.at ?? null,
    announcement,
  };
}
