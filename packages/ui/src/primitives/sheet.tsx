'use client';

import { X } from 'lucide-react';
import { useEffect, useRef, type HTMLAttributes, type KeyboardEvent, type ReactNode } from 'react';

import { cn } from '../lib/cn';
import { focusTokens } from '../tokens/tokens';

/** Everything a keyboard user can land on inside the sheet. */
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'details > summary',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

function focusableWithin(root: HTMLElement): HTMLElement[] {
  // `hidden` is the only visibility signal that survives jsdom (no layout there), and
  // in the browser anything display:none also has no client rects.
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) =>
      element.closest('[hidden]') === null &&
      (typeof element.getClientRects !== 'function' ||
        element.getClientRects().length > 0 ||
        element === document.activeElement ||
        // jsdom: every rect list is empty; fall back to treating the element as visible.
        root.getClientRects().length === 0),
  );
}

export interface ContextSheetProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  /** Which edge of the stage the sheet slides over. */
  side: 'left' | 'right';
  open: boolean;
  /** Called for the close button and Escape. The owner drops `open`. */
  onClose: () => void;
  /** Accessible name of the dialog, and its header eyebrow. */
  label: string;
  /** Optional subject line under the eyebrow — what the sheet is currently about. */
  subject?: string | null;
  /**
   * True when the content fills the sheet and scrolls internally (a chat log);
   * false (default) lets the sheet scroll a stack of panels.
   */
  fill?: boolean;
  children?: ReactNode;
  'data-testid'?: string;
}

/**
 * A context sheet: transient deep material sliding over the stage, tethered to the edge
 * of its side. It is a dialog for focus purposes — focus moves in on open, Tab cycles
 * inside, Escape closes, and focus returns to where the operator was — but it is not
 * modal: the stage stays pointer-live around it, because summoning context must never
 * take the world away.
 *
 * The owner controls `open` and width (via `className`); the sheet owns chrome, focus
 * and dismissal. Entry is a motion-safe slide; reduced motion swaps to instant
 * appearance via the global motion kill-switch.
 */
export function ContextSheet({
  side,
  open,
  onClose,
  label,
  subject,
  fill = false,
  children,
  className,
  'data-testid': testId,
  ...rest
}: ContextSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  // Dialog focus contract: remember where the operator was, move focus into the sheet,
  // and hand it back when the sheet leaves.
  useEffect(() => {
    if (!open) {
      return;
    }
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
    return () => {
      const restore = restoreFocusRef.current;
      if (restore && restore.isConnected) {
        restore.focus();
      }
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      // The sheet owns Escape while focus is inside it; without the stop the cockpit's
      // global Escape would also fire and close the next surface down in the same press.
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') {
      return;
    }
    const panel = panelRef.current;
    if (!panel) {
      return;
    }
    const focusable = focusableWithin(panel);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (first === undefined || last === undefined) {
      event.preventDefault();
      return;
    }
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === panel)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-label={label}
      tabIndex={-1}
      data-testid={testId}
      data-side={side}
      onKeyDown={handleKeyDown}
      className={cn(
        'absolute inset-y-0 z-40 flex flex-col overflow-hidden border border-[var(--aegis-border-strong)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl',
        side === 'right'
          ? 'right-0 rounded-l-[var(--aegis-radius-lg)] aegis-sheet-enter-right'
          : 'left-0 rounded-r-[var(--aegis-radius-lg)] aegis-sheet-enter-left',
        focusTokens.ring,
        className,
      )}
      {...rest}
    >
      <div className="flex items-start gap-2 border-b border-[var(--aegis-border-subtle)] px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
            {label}
          </p>
          {subject ? (
            <p className="mt-0.5 truncate text-sm font-semibold text-[var(--aegis-text-primary)]">
              {subject}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          data-testid={testId ? `${testId}-close` : undefined}
          aria-label={`Close ${label.toLowerCase()}`}
          onClick={onClose}
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--aegis-radius-md)] border border-transparent text-[var(--aegis-text-muted)] transition-[background-color,border-color,color] hover:border-[var(--aegis-border-default)] hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)]',
            focusTokens.ring,
          )}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div
        className={cn(
          'flex min-h-0 flex-1 flex-col p-3',
          fill ? 'overflow-hidden' : 'overflow-y-auto',
        )}
      >
        {children}
      </div>
    </div>
  );
}
