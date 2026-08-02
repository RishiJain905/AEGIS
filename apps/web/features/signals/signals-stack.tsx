'use client';

import { useCallback, useEffect } from 'react';

import { cn } from '@aegis/ui';

import { useRunActivity } from '@/features/live-run';
import { AlertsTab } from '@/features/shell/components/alerts-tab';
import { useRunAlerts } from '@/features/shell/hooks/use-shell-queries';
import { resolveSignalsState, useCockpitUiStore } from '@/stores/cockpit-ui-store';

/** Severity order for the capsule's worst-severity tint; first match wins. */
const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const;

const SEVERITY_TINT: Record<string, string> = {
  critical: 'var(--aegis-risk-critical)',
  high: 'var(--aegis-risk-high)',
  medium: 'var(--aegis-risk-medium)',
  low: 'var(--aegis-risk-low)',
};

function worstSeverity(alerts: readonly { severity: string }[]): string | null {
  for (const severity of SEVERITY_ORDER) {
    if (alerts.some((alert) => alert.severity.toLowerCase() === severity)) {
      return severity;
    }
  }
  return alerts.length > 0 ? 'medium' : null;
}

/** True when the key event belongs to a typing context, not the cockpit. */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT' ||
    target.isContentEditable
  );
}

/**
 * The capsule's own tiny activity reading — recent weighted event pressure as a short
 * bar strip. The full ActivityStrip lives inside the alerts panel (untouched); this is
 * the ambient version that survives collapse, because "is anything happening" must be
 * answerable without opening anything.
 */
function CapsulePulse() {
  const activity = useRunActivity();
  const peak = Math.max(1, ...activity.buckets);
  const recent = activity.buckets.slice(-8);

  return (
    <span
      className="flex h-4 items-end gap-[2px]"
      role="img"
      aria-label={`Run activity: ${String(activity.count)} events in the last ${String(activity.windowSeconds)} seconds of simulated time.`}
      data-level={activity.level}
    >
      {recent.map((value, index) => (
        <span
          key={index}
          className="w-[3px] rounded-[1px]"
          style={{
            height: `${String(Math.max(20, Math.round((value / peak) * 100)))}%`,
            backgroundColor: value > 0 ? 'currentColor' : 'var(--aegis-border-subtle)',
            opacity: value > 0 ? 0.9 : 0.5,
          }}
        />
      ))}
    </span>
  );
}

export interface SignalsStackProps {
  runId: string;
}

/**
 * Signals — the alerts surface as ambient attention pressure over the stage's top-right,
 * instead of a dock tab 800px from the nodes it names.
 *
 * Two states, never zero: an expanded stack of the existing alert cards (internals
 * untouched — this component only re-containers `AlertsTab`), or a single capsule
 * carrying the activity pulse, the alert count and the worst live severity as its tint.
 * It is never fully dismissible; ambient awareness is the point of a SOC. With no
 * explicit operator choice the stack resolves automatically — expanded while alerts
 * exist, capsule while the floor is quiet — so the first alert of a run opens it.
 *
 * Collision rule: when the inspector sheet claims the right side, the stack force-
 * collapses to its capsule docked at the sheet's top edge, and expanding it opens the
 * stack as an overlay OVER the sheet (never widening the total claim on the stage).
 */
export function SignalsStack({ runId }: SignalsStackProps) {
  const alertsQuery = useRunAlerts(runId);
  const alerts = alertsQuery.data ?? [];
  const alertCount = alerts.length;
  const worst = worstSeverity(alerts);

  const preference = useCockpitUiStore((state) => state.signalsPreference);
  const setPreference = useCockpitUiStore((state) => state.setSignalsPreference);
  const inspectorSheetOpen = useCockpitUiStore((state) => state.inspectorSheetOpen);
  const overlayOpen = useCockpitUiStore((state) => state.signalsOverlayOpen);
  const setOverlayOpen = useCockpitUiStore((state) => state.setSignalsOverlayOpen);

  const resolved = resolveSignalsState(preference, alertCount);
  // The collision rule is a hard rule, not a negotiation: an open right sheet forces the
  // capsule; the stack only reappears as an overlay owned by the sheet's space.
  const showExpandedStack = !inspectorSheetOpen && resolved === 'expanded';
  const showOverlay = inspectorSheetOpen && overlayOpen;

  const expand = useCallback(() => {
    if (inspectorSheetOpen) {
      setOverlayOpen(true);
    } else {
      setPreference('expanded');
    }
  }, [inspectorSheetOpen, setOverlayOpen, setPreference]);

  const collapse = useCallback(() => {
    if (inspectorSheetOpen) {
      setOverlayOpen(false);
    } else {
      setPreference('capsule');
    }
  }, [inspectorSheetOpen, setOverlayOpen, setPreference]);

  const isOpen = showExpandedStack || showOverlay;

  // `A` toggles the stack from anywhere that is not a typing context.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== 'a' ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        event.defaultPrevented ||
        isTypingTarget(event.target)
      ) {
        return;
      }
      event.preventDefault();
      if (isOpen) {
        collapse();
      } else {
        expand();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, expand, collapse]);

  const tint = worst ? SEVERITY_TINT[worst] : 'var(--aegis-text-muted)';

  if (!isOpen) {
    return (
      <button
        type="button"
        data-testid="signals-capsule"
        data-severity={worst ?? 'none'}
        data-docked={inspectorSheetOpen ? 'sheet' : 'stage'}
        aria-expanded={false}
        title="Signals (A)"
        onClick={expand}
        className="absolute right-3 top-24 z-30 flex items-center gap-2.5 rounded-full border bg-[color-mix(in_srgb,var(--aegis-surface-panel)_92%,transparent)] px-3 py-1.5 shadow-[var(--aegis-shadow-control)] backdrop-blur-xl transition-colors hover:bg-[var(--aegis-surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
        style={{
          borderColor: `color-mix(in srgb, ${tint} 45%, transparent)`,
          color: tint,
        }}
      >
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.16em]">
          Signals
        </span>
        <CapsulePulse />
        <span
          data-testid="signals-count"
          className="font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] tabular-nums"
        >
          {alertCount}
        </span>
      </button>
    );
  }

  return (
    <section
      role="region"
      aria-label="Signals"
      data-testid="signals-stack"
      data-mode={showOverlay ? 'overlay' : 'stack'}
      className={cn(
        'absolute right-3 top-24 z-30 flex max-h-[40vh] w-[min(22rem,86%)] flex-col overflow-hidden rounded-[var(--aegis-radius-lg)] border border-[var(--aegis-border-subtle)] bg-[color-mix(in_srgb,var(--aegis-surface-panel)_92%,transparent)] shadow-[var(--aegis-shadow-panel)] backdrop-blur-xl',
      )}
    >
      <div className="flex items-center gap-2 border-b border-[var(--aegis-border-subtle)] px-3 py-2">
        <span className="font-[family-name:var(--aegis-font-display)] text-[0.625rem] font-semibold uppercase tracking-[0.16em] text-[var(--aegis-text-muted)]">
          Signals
        </span>
        <span
          data-testid="signals-count"
          className="font-[family-name:var(--aegis-font-mono)] text-[0.6875rem] tabular-nums"
          style={{ color: tint }}
        >
          {alertCount}
        </span>
        <button
          type="button"
          data-testid="signals-collapse"
          aria-expanded={true}
          aria-label="Collapse signals"
          title="Collapse signals (A)"
          onClick={collapse}
          className="ml-auto rounded-[var(--aegis-radius-sm)] px-2 py-1 font-[family-name:var(--aegis-font-mono)] text-[10px] uppercase tracking-wide text-[var(--aegis-text-muted)] transition-colors hover:bg-[var(--aegis-surface-hover)] hover:text-[var(--aegis-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--aegis-focus-ring)]"
        >
          Collapse
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <AlertsTab runId={runId} />
      </div>
    </section>
  );
}
