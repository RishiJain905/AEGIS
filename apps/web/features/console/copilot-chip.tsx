'use client';

import { useEffect, useState } from 'react';

import { cn, useReducedMotion } from '@aegis/ui';

import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

import { PREVIEW_VISIBLE_MS, useCopilotPresence } from './use-copilot-presence';

/** The copilot's glyph — the console's summon mark for the colleague. */
function RoleGlyph({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className={cn('h-3.5 w-3.5', className)}>
      <path
        d="M8 1.5 14.5 8 8 14.5 1.5 8Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="8" r="1.6" fill="currentColor" />
    </svg>
  );
}

export interface CopilotChipProps {
  runId: string;
}

/**
 * The copilot presence chip — the console's always-visible handle on the agents, and the
 * summon for the copilot sheet. It is a state machine with unmissable, non-modal
 * transitions:
 *
 * - idle: glyph + name, quiet;
 * - working: the per-role task state, alive for the whole turn (motion-safe ring sweep;
 *   reduced motion swaps to a static "working…" label);
 * - unread / failed: a gold (or risk-tinted) badge that persists until the sheet opens,
 *   plus a one-line preview of the reply beside the chip for a few seconds before it
 *   folds into the badge. An `aria-live` region says the same thing to screen readers.
 *
 * Nothing here is modal and nothing auto-opens the sheet; the chip only ever invites.
 */
export function CopilotChip({ runId }: CopilotChipProps) {
  const presence = useCopilotPresence(runId);
  const setSheetOpen = useCockpitUiStore((state) => state.setCopilotSheetOpen);
  const sheetOpen = useCockpitUiStore((state) => state.copilotSheetOpen);
  const reducedMotion = useReducedMotion();

  // The preview line shows for a few seconds per unread event, then folds into the badge.
  const [previewVisible, setPreviewVisible] = useState(false);
  useEffect(() => {
    if (presence.lastEventAt === null || presence.preview === null) {
      setPreviewVisible(false);
      return;
    }
    setPreviewVisible(true);
    const timer = setTimeout(() => {
      setPreviewVisible(false);
    }, PREVIEW_VISIBLE_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [presence.lastEventAt, presence.preview]);

  const working = presence.phase === 'working';
  const failed = presence.phase === 'failed';
  const unread = presence.phase === 'unread' || failed;

  const label = working
    ? (presence.workingRoles[0] ?? 'Copilot')
    : failed
      ? 'Needs attention'
      : 'Copilot';

  const accessibleName = working
    ? `Copilot — ${presence.workingRoles.join(', ')} working. Open copilot.`
    : unread
      ? `Copilot — ${String(presence.unreadCount)} unread ${failed ? 'including a failure' : 'replies'}. Open copilot.`
      : 'Open copilot';

  return (
    <div className="flex min-w-0 items-center gap-2">
      <button
        type="button"
        data-testid="copilot-chip"
        data-phase={presence.phase}
        aria-label={accessibleName}
        aria-expanded={sheetOpen}
        title="Copilot (C)"
        onClick={() => {
          setSheetOpen(true);
        }}
        className={cn(
          'flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]',
          failed
            ? 'border-[color-mix(in_srgb,var(--aegis-risk-critical)_60%,transparent)] text-[var(--aegis-risk-critical)] hover:bg-[color-mix(in_srgb,var(--aegis-risk-critical)_10%,transparent)]'
            : unread
              ? 'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-strong)] hover:bg-[var(--aegis-surface-hover)]'
              : 'border-[var(--aegis-border-subtle)] text-[var(--aegis-text-secondary)] hover:border-[var(--aegis-border-strong)] hover:text-[var(--aegis-text-primary)]',
          unread && !reducedMotion && previewVisible && 'motion-safe:animate-pulse',
        )}
      >
        {working && !reducedMotion ? (
          <span
            aria-hidden="true"
            data-testid="copilot-chip-ring"
            className="h-3.5 w-3.5 shrink-0 rounded-full border-[1.5px] border-[var(--aegis-accent)] border-t-transparent motion-safe:animate-spin"
          />
        ) : (
          <RoleGlyph />
        )}
        <span className="max-w-[9rem] truncate">
          {working && reducedMotion ? `${label} working…` : label}
        </span>
        {unread && presence.unreadCount > 0 ? (
          <span
            data-testid="copilot-chip-unread"
            className={cn(
              'rounded-full border px-1.5 py-px font-[family-name:var(--aegis-font-mono)] text-[9px] leading-4 tabular-nums',
              failed
                ? 'border-[color-mix(in_srgb,var(--aegis-risk-critical)_60%,transparent)] text-[var(--aegis-risk-critical)]'
                : 'border-[var(--aegis-accent-line)] bg-[var(--aegis-accent-soft)] text-[var(--aegis-accent-strong)]',
            )}
          >
            {presence.unreadCount}
          </span>
        ) : null}
      </button>

      {previewVisible && presence.preview ? (
        <span
          data-testid="copilot-chip-preview"
          className="max-w-[16rem] truncate text-xs text-[var(--aegis-text-secondary)]"
        >
          {presence.previewRole ? `${presence.previewRole}: ` : ''}
          {presence.preview}
        </span>
      ) : null}

      <span role="status" aria-live="polite" className="sr-only">
        {presence.announcement}
      </span>
    </div>
  );
}
