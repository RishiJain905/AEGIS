'use client';

import { useEffect } from 'react';

import { cn } from '@aegis/ui';

import type { OperatorActionResponse } from '@/features/command-surface';

export interface ActionResult {
  commandLabel: string;
  assetLabel: string;
  response: OperatorActionResponse | null;
  /** Present when the request itself failed (network/policy error envelope). */
  errorMessage?: string;
}

const AUTO_DISMISS_MS = 6_000;

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

const TONE_CLASS: Record<'ok' | 'warn' | 'block', string> = {
  ok: 'border-[color-mix(in_srgb,var(--aegis-accent-cyan)_60%,transparent)]',
  warn: 'border-[color-mix(in_srgb,var(--aegis-risk-medium)_60%,transparent)]',
  block: 'border-[color-mix(in_srgb,var(--aegis-risk-high)_65%,transparent)]',
};

/**
 * Transient result notification for an operator action. Honest by construction: a policy
 * block reads "Blocked by policy" with its reason codes, never a false success. Auto-dismisses;
 * under reduced motion it appears without a transition.
 */
export function ActionResultToast({
  result,
  onDismiss,
}: {
  result: ActionResult;
  onDismiss: () => void;
}) {
  const { tone, headline } = toneFor(result);

  useEffect(() => {
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [onDismiss]);

  const detail =
    result.errorMessage ??
    (result.response?.status === 'blocked'
      ? result.response.reasonCodes.join(', ') || 'The policy engine rejected this action.'
      : result.response?.status === 'confirmation_required'
        ? 'This action needs your confirmation as incident commander.'
        : `${result.commandLabel} on ${result.assetLabel}.`);

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="action-result-toast"
      className={cn(
        'fixed bottom-6 right-6 z-50 w-80 max-w-[calc(100vw-3rem)] rounded-[var(--aegis-radius-lg)] border bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] px-4 py-3 shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl',
        TONE_CLASS[tone],
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <p className="font-[family-name:var(--aegis-font-display)] text-sm font-semibold text-[var(--aegis-text-primary)]">
            {headline}
          </p>
          <p className="text-xs leading-4 text-[var(--aegis-text-secondary)]">{detail}</p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="shrink-0 rounded-[var(--aegis-radius-sm)] px-1 text-[var(--aegis-text-muted)] hover:text-[var(--aegis-text-primary)]"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
