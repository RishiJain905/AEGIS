'use client';

import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import { cn } from '@aegis/ui';

import type { OperatorActionResponse } from '@/features/command-surface';

import { useActionResultSlot } from './action-result-slot';

export interface ActionResult {
  commandLabel: string;
  assetLabel: string;
  response: OperatorActionResponse | null;
  /** Present when the request itself failed (network/policy error envelope). */
  errorMessage?: string;
}

const AUTO_DISMISS_MS = 7_000;

function toneFor(result: ActionResult): {
  tone: 'ok' | 'warn' | 'block';
  headline: string;
} {
  if (result.errorMessage) {
    return { tone: 'block', headline: 'Action failed' };
  }
  const response = result.response;
  if (!response) {
    return { tone: 'warn', headline: 'Action submitted' };
  }
  if (response.status === 'blocked') {
    return { tone: 'block', headline: 'Blocked by policy' };
  }
  if (response.status === 'confirmation_required') {
    return { tone: 'warn', headline: 'Confirmation required' };
  }
  return { tone: 'ok', headline: response.executed ? 'Action executed' : 'Action ordered' };
}

const TONE_RAIL: Record<'ok' | 'warn' | 'block', string> = {
  ok: 'var(--aegis-accent-cyan)',
  warn: 'var(--aegis-risk-medium)',
  block: 'var(--aegis-risk-high)',
};

/**
 * Transient result notification for an operator action. Honest by construction: a policy
 * block reads "Blocked by policy" with its reason codes, never a false success.
 *
 * It renders into the console's result rail — a laid-out row directly above the command
 * band, in the same voice as the frozen-timeline notice — so a result rises out of the
 * hands that ordered it. It is never a floating card over the corner of the console, which
 * is what made it swallow clicks on the very verbs it was reporting on. Reduced motion
 * drops the entry animation through the global motion kill switch.
 */
export function ActionResultToast({
  result,
  onDismiss,
}: {
  result: ActionResult;
  onDismiss: () => void;
}) {
  const { tone, headline } = toneFor(result);
  const slot = useActionResultSlot();

  // The dismiss callback is re-created on every render of the surface that owns the runner,
  // and a live run re-renders that surface constantly. Keying the timer on the callback
  // therefore restarted it several times a second and the notification never left. The
  // timer belongs to the *result*; the callback rides in a ref.
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;
  useEffect(() => {
    const timer = window.setTimeout(() => {
      onDismissRef.current();
    }, AUTO_DISMISS_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [result]);

  const detail =
    result.errorMessage ??
    (result.response?.status === 'blocked'
      ? result.response.reasonCodes.join(', ') || 'The policy engine rejected this action.'
      : result.response?.status === 'confirmation_required'
        ? 'This action needs your confirmation as incident commander.'
        : `${result.commandLabel} on ${result.assetLabel}.`);

  const card = (
    <div
      role="status"
      aria-live="polite"
      data-testid="action-result-toast"
      data-tone={tone}
      className={cn(
        'flex w-full max-w-[30rem] items-start gap-3 rounded-[var(--aegis-radius-md)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] py-2 pl-3 pr-2 shadow-[var(--aegis-shadow-control)] backdrop-blur-xl',
        'aegis-sheet-enter-up',
        // Only the fallback (no console mounted) needs to place itself; inside the rail the
        // row is laid out, so it cannot sit over anything.
        slot === null && 'mx-auto',
      )}
    >
      <span
        aria-hidden="true"
        className="mt-0.5 h-8 w-0.5 shrink-0 rounded-full"
        style={{ backgroundColor: TONE_RAIL[tone] }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <p
          className="font-[family-name:var(--aegis-font-display)] text-[0.6875rem] font-semibold uppercase tracking-[0.14em]"
          style={{ color: TONE_RAIL[tone] }}
        >
          {headline}
        </p>
        <p className="text-xs leading-4 text-[var(--aegis-text-secondary)]">{detail}</p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="shrink-0 rounded-[var(--aegis-radius-sm)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)] transition-colors hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
      >
        Dismiss
      </button>
    </div>
  );

  return slot === null ? card : createPortal(card, slot);
}
