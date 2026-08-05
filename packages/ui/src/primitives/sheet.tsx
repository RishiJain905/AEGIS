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

/**
 * The last element the operator actually focused, tracked document-wide.
 *
 * A sheet cannot learn its invoker from `document.activeElement` at effect time: the store
 * update that opens the sheet is the same one that can fold the surface the invoker lived on
 * (an alert card's asset button dies when the signals stack collapses for the sheet), and by
 * the time effects run the DOM is already re-committed with focus back on `<body>`. Watching
 * `focusin` in the capture phase records the invoker while it is still real.
 */
let lastFocusedElement: HTMLElement | null = null;
let focusTrackerInstalled = false;

function trackFocus(event: FocusEvent) {
  if (event.target instanceof HTMLElement && event.target !== document.body) {
    lastFocusedElement = event.target;
  }
}

function installFocusTracker(): void {
  if (focusTrackerInstalled || typeof document === 'undefined') {
    return;
  }
  focusTrackerInstalled = true;
  document.addEventListener('focusin', trackFocus, true);
}

/** Exported for tests; the tracker is process-wide and otherwise never reset. */
export function resetSheetFocusTracking(): void {
  lastFocusedElement = null;
}

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
  side: 'left' | 'right' | 'bottom';
  open: boolean;
  /** Called for the close button and Escape. The owner drops `open`. */
  onClose: () => void;
  /** Accessible name of the dialog, and its header eyebrow. */
  label: string;
  /** Optional subject line under the eyebrow — what the sheet is currently about. */
  subject?: string | null;
  /**
   * The subject's identity, when its display name is not it. Rendered under the subject as
   * a quiet mono line so the operator reads the name first and can still copy the id.
   */
  subjectDetail?: string | null;
  /**
   * Where focus goes when the sheet closes and the element that summoned it no longer
   * exists — a card that folded away while the sheet was open. Without it focus falls to
   * `<body>` and the keyboard operator loses their place.
   */
  restoreFocusTo?: () => HTMLElement | null;
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
  subjectDetail,
  restoreFocusTo,
  fill = false,
  children,
  className,
  'data-testid': testId,
  ...rest
}: ContextSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const restoreFocusToRef = useRef(restoreFocusTo);
  restoreFocusToRef.current = restoreFocusTo;

  useEffect(installFocusTracker, []);

  // Dialog focus contract: remember where the operator was, move focus into the sheet,
  // and hand it back when the sheet leaves.
  useEffect(() => {
    if (!open) {
      return;
    }
    const panel = panelRef.current;
    const active = document.activeElement;
    const invoker =
      active instanceof HTMLElement && active !== document.body ? active : lastFocusedElement;
    restoreFocusRef.current = invoker && !panel?.contains(invoker) ? invoker : null;
    // Content inside the sheet may have claimed focus already — a composer seeded by the
    // keystroke that summoned the sheet. Children's effects run first, so pulling focus
    // back to the panel here would swallow the operator's next keystrokes.
    if (panel && !panel.contains(document.activeElement)) {
      panel.focus();
    }
    return () => {
      const restore = restoreFocusRef.current;
      if (restore?.isConnected) {
        restore.focus();
        return;
      }
      restoreFocusToRef.current?.()?.focus();
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
        'absolute z-40 flex flex-col overflow-hidden border border-[var(--aegis-border-strong)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_94%,transparent)] shadow-[var(--aegis-shadow-dialog)] backdrop-blur-xl',
        side === 'right' &&
          'inset-y-0 right-0 rounded-l-[var(--aegis-radius-lg)] aegis-sheet-enter-right',
        side === 'left' &&
          'inset-y-0 left-0 rounded-r-[var(--aegis-radius-lg)] aegis-sheet-enter-left',
        side === 'bottom' &&
          'inset-x-0 bottom-0 rounded-t-[var(--aegis-radius-lg)] aegis-sheet-enter-up',
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
            <p
              data-testid={testId ? `${testId}-subject` : undefined}
              className="mt-0.5 truncate text-sm font-semibold text-[var(--aegis-text-primary)]"
            >
              {subject}
            </p>
          ) : null}
          {subjectDetail ? (
            <p
              data-testid={testId ? `${testId}-subject-detail` : undefined}
              className="truncate font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] leading-4 text-[var(--aegis-text-muted)]"
            >
              {subjectDetail}
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
